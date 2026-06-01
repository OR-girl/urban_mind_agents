#!/usr/bin/env python3
"""SmartRoute Agent — Web Server. Usage: python server.py → http://localhost:8000"""
from __future__ import annotations
import asyncio, json, sys, time, traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

from smartroute.core.config import get_settings
from smartroute.mock.services import MockServiceLayer
from smartroute.schemas.state import SystemState


class PipelineExecutor:
    def __init__(self): self.mock = MockServiceLayer()

    async def run(self, query: str, session_id: str):
        state = SystemState(session_id=session_id, trace_id=f"trace_{session_id}", request_type="NEW", raw_query=query, dialog_history=[])
        total_start = time.time()

        # Stage 1: Intent
        yield self._sse_status("intent", "正在理解您的需求...")
        intent_success = False
        for attempt_query in [query, query + " 在杭州"]:
            try:
                from smartroute.agents.intent import IntentAgent
                agent = IntentAgent()
                result = await agent.execute(state)
                state.intent = result.get("intent")
                state.clarification_needed = result.get("clarification_needed", False)
                if not state.clarification_needed: intent_success = True; break
                state.raw_query = attempt_query
            except Exception: pass
        if not intent_success or state.clarification_needed:
            state.intent = self._fallback_intent(query); state.clarification_needed = False

        intent = state.get_intent()
        if intent:
            yield self._sse_status("intent", f"识别意图: {intent.intent_type.value} | 城市: {intent.spatial.city}")
            yield self._sse_message({"type": "intent", "intent": state.intent})

        # Stage 2: Retrieval
        yield self._sse_status("retrieval", "正在搜索 POI 候选集...")
        candidates = self.mock.retrieve_candidates(intent, top_k=15) if intent else []
        state.candidates = candidates
        yield self._sse_status("retrieval", f"召回 {len(candidates)} 个候选 POI")
        yield self._sse_message({"type": "candidates", "candidates": candidates[:12]})

        # Stage 3: UGC
        yield self._sse_status("ugc", "DeepSeek + NLP 双通道分析评论...")
        enriched = await self._run_ugc(candidates)
        state.enriched_pois = enriched
        yield self._sse_status("ugc", f"完成 {len(enriched)} 个 POI 洞察分析")
        yield self._sse_message({"type": "insights", "enriched_pois": enriched})

        # Stage 4: Route
        yield self._sse_status("route", "多约束优化求解路线...")
        routes = self._build_routes(enriched)
        state.routes = routes
        yield self._sse_status("route", f"生成 {len(routes)} 套差异化方案")

        # Stage 5: Presentation
        yield self._sse_status("presentation", "生成个性化方案...")
        final = await self._run_presentation(routes, enriched, intent)
        meta_plans = [{"plan_id": r.get("plan_id"), "name": r.get("name"), "tagline": r.get("tagline"), "summary": r.get("summary", {})} for r in routes]
        yield self._sse_message({"type": "structured_meta", "plans": meta_plans, "session_id": session_id, "summary": final.get("summary", "")})

        # Stream LLM text
        stream_prompt = self._build_stream_prompt(routes)
        try:
            from smartroute.services.llm.router import LLMRouter
            router = LLMRouter()
            async for token in router.stream(messages=[{"role": "user", "content": stream_prompt}], temperature=0.7, max_tokens=800):
                yield self._sse_text(token)
        except Exception: yield self._sse_text(final.get("summary", ""))

        yield self._sse_message({"type": "structured", "plans": routes, "session_id": session_id, "plan_comparison": final.get("plan_comparison", {}), "adjustable_hints": final.get("adjustable_hints", [])})
        yield self._sse_status("presentation", f"规划完成，总耗时 {round(time.time()-total_start,1)}s")

    async def run_adjust(self, query: str, session_id: str):
        yield self._sse_status("intent", "理解调整需求...")
        state = SystemState(session_id=session_id, trace_id=f"trace_{session_id}", request_type="MODIFY", raw_query=query, dialog_history=[])
        existing = await self.mock.load_session(session_id) or {}
        if existing.get("intent"): state.intent = existing["intent"]
        candidates = self.mock.retrieve_candidates(state.get_intent(), top_k=15) if state.get_intent() else []
        state.candidates = candidates
        yield self._sse_status("retrieval", f"召回 {len(candidates)} 个 POI")
        enriched = await self._run_ugc(candidates); state.enriched_pois = enriched
        yield self._sse_status("ugc", f"完成 {len(enriched)} 个 POI")
        routes = self._build_routes_adjusted(enriched, query); state.routes = routes
        yield self._sse_status("route", f"生成 {len(routes)} 套调整方案")
        final = await self._run_presentation(routes, enriched, state.get_intent())
        yield self._sse_message({"type": "structured_meta", "plans": [{"plan_id": r.get("plan_id"), "name": r.get("name"), "tagline": r.get("tagline"), "summary": r.get("summary", {})} for r in routes], "session_id": session_id, "summary": f"根据「{query}」调整后的方案："})
        try:
            from smartroute.services.llm.router import LLMRouter
            async for token in LLMRouter().stream(messages=[{"role": "user", "content": f"用户对路线提出调整：「{query}」。请用1-2句话说明调整后的变化。"}], temperature=0.7, max_tokens=400):
                yield self._sse_text(token)
        except Exception: yield self._sse_text(f"已根据「{query}」重新规划。")
        yield self._sse_message({"type": "structured", "plans": routes, "session_id": session_id, "plan_comparison": final.get("plan_comparison", {}), "adjustable_hints": final.get("adjustable_hints", [])})
        await self.mock.save_session(session_id, {"intent": state.intent, "candidates": candidates, "enriched_pois": enriched, "routes": routes})

    async def _run_ugc(self, candidates):
        from smartroute.agents.ugc.llm_channel import get_llm_channel
        from smartroute.agents.ugc.nlp_analyzer import NLPAnalyzer
        llm_ch, nlp = get_llm_channel(), NLPAnalyzer()
        enriched, llm_pois = [], [p for p in candidates if p.get("review_count",0)>=100][:5]
        processed = {p["poi_id"] for p in llm_pois}
        if llm_pois:
            sem = asyncio.Semaphore(3)
            async def a1(p):
                async with sem:
                    try: return await llm_ch.analyze(p, self.mock.get_reviews_for_poi(p["poi_id"]))
                    except Exception: return nlp.analyze(p, self.mock.get_reviews_for_poi(p["poi_id"]))
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*[a1(p) for p in llm_pois], return_exceptions=True),
                    timeout=45.0)
            except asyncio.TimeoutError:
                results = [nlp.analyze(p, self.mock.get_reviews_for_poi(p["poi_id"])) for p in llm_pois]
            for p, r in zip(llm_pois, results):
                if isinstance(r, Exception): r = nlp.analyze(p, self.mock.get_reviews_for_poi(p["poi_id"]))
                for k in ("poi_id","name","category"): r.setdefault(k, p.get(k,""))
                r.setdefault("avg_cost",p.get("avg_cost",0)); r.setdefault("rating",p.get("rating",0))
                enriched.append(r)
        for p in candidates:
            if p["poi_id"] not in processed:
                r = nlp.analyze(p, self.mock.get_reviews_for_poi(p["poi_id"]))
                for k in ("poi_id","name","category"): r.setdefault(k, p.get(k,""))
                r.setdefault("avg_cost",p.get("avg_cost",0)); r.setdefault("rating",p.get("rating",0))
                enriched.append(r); processed.add(p["poi_id"])
        return enriched

    def _build_routes(self, enriched):
        rst=[p for p in enriched if "餐" in p.get("category","")]; att=[p for p in enriched if "景点" in p.get("category","")]
        tea=[p for p in enriched if "茶" in p.get("category","")]; oth=[p for p in enriched if p not in rst and p not in att and p not in tea]
        strategies=[("经典稳妥","兼顾体验与效率，适合首次到访",(att[:3] if att else[])+(rst[:2] if rst else[])+(tea[:1] if tea else[])+oth[:1]),
                     ("避峰省时","规避排队高峰，时间利用率最高",sorted((att[:2] if att else[])+(rst[:2] if rst else[])+oth[:1],key=lambda p:p.get("review_count",10**9))),
                     ("极致体验","不惜排队，追求最佳体验",sorted((rst[:3] if rst else[])+(att[:2] if att else[])+(tea[:1] if tea else[]),key=lambda p:p.get("rating",0),reverse=True))]
        return self._build_timelines(strategies)

    def _build_routes_adjusted(self, enriched, adjust_query):
        q=adjust_query.lower(); sorted_p=sorted(enriched,key=lambda p:p.get("avg_cost",0)or 0) if any(k in q for k in('便宜','省钱','贵','预算')) else sorted(enriched,key=lambda p:p.get("rating",0)or 0,reverse=True)
        rst=[p for p in sorted_p if "餐" in p.get("category","")]; att=[p for p in sorted_p if "景点" in p.get("category","")]
        tea=[p for p in sorted_p if "茶" in p.get("category","")]; oth=[p for p in sorted_p if p not in rst and p not in att and p not in tea]
        return self._build_timelines([(f"调整方案",f"基于「{adjust_query}」的优化路线",(att[:2] if att else[])+(rst[:2] if rst else[])+(tea[:1] if tea else[])+oth[:1])])

    def _build_timelines(self, strategies):
        routes=[]
        for i,(name,tagline,seq) in enumerate(strategies):
            if i>0: used={item["poi_id"] for r in routes for item in r["timeline"]}; seq=[p for p in seq if p["poi_id"] not in used]
            seq=seq[:5]
            if len(seq)<2: continue
            tl,cm,total_cost,total_walk=[],540,0,0
            for j,p in enumerate(seq):
                dur=p.get("estimated_duration_min",60); cost=p.get("avg_cost",0)or 0; total_cost+=cost
                w=0
                if j<len(seq)-1: w=self.mock.get_distance_matrix([p["poi_id"],seq[j+1]["poi_id"]])[0][1]; total_walk+=w
                a=f"{cm//60:02d}:{cm%60:02d}"; lm=cm+dur; l=f"{lm//60:02d}:{lm%60:02d}"
                tl.append({"poi_id":p["poi_id"],"poi_name":p["name"],"category":p["category"],"arrive_time":a,"leave_time":l,"duration_min":dur,"estimated_cost":cost,"highlights":p.get("highlights",[]),"warnings":p.get("warnings",[]),"queue_warning":p.get("queue_warning",""),"transport_to_next":{"mode":"步行","duration_min":w,"distance_m":w*80} if j<len(seq)-1 else{}})
                cm=lm+w
            routes.append({"plan_id":f"plan_{chr(97+i)}","name":name,"tagline":tagline,"timeline":tl,"summary":{"total_cost":total_cost,"total_distance_km":round(total_walk*0.08,1),"total_duration_h":round((cm-540)/60,1),"poi_count":len(seq)},"is_feasible":True})
        return routes

    async def _run_presentation(self, routes, enriched, intent):
        emap={p["poi_id"]:p for p in enriched}
        try:
            from smartroute.agents.presentation.reason_generator import PersonalizedReasonGenerator
            reasons=await PersonalizedReasonGenerator().batch_generate(routes=routes,enriched_map=emap,profile=None,intent=intent)
        except Exception: reasons={}
        for r in routes:
            for item in r.get("timeline",[]): item["why_for_you"]=reasons.get(item["poi_id"],f"{item.get('poi_name','')}，值得一游")
        names=" / ".join(r["name"] for r in routes)
        costs=[r.get("summary",{}).get("total_cost",0)or 0 for r in routes]; mc=min(costs)if costs else 0
        scene=intent.intent_type.value if intent else "出行"
        from smartroute.agents.presentation.comparison import PlanComparisonGenerator
        from smartroute.agents.presentation.hints import AdjustableHintsGenerator
        return {"summary":f"为您定制了 {len(routes)} 套{scene}方案：{names}，最低 ¥{mc}/人","plan_comparison":PlanComparisonGenerator().generate(routes),"adjustable_hints":AdjustableHintsGenerator().generate(routes,emap)}

    def _fallback_intent(self, query):
        from smartroute.schemas.intent import IntentResult,IntentType,SpatialConstraint,TemporalConstraint,PartyInfo,Preferences,BudgetInfo
        return IntentResult(intent_type=IntentType.TOUR,confidence=0.5,spatial=SpatialConstraint(city="杭州"),temporal=TemporalConstraint(date=datetime.now().strftime("%Y-%m-%d")),party=PartyInfo(),preferences=Preferences(),budget=BudgetInfo(),raw_query=query).model_dump()

    def _build_stream_prompt(self, routes):
        return f"请用2-3句话简要介绍以下{len(routes)}个路线方案。语气自然亲切。\n{json.dumps([{'name':r.get('name'),'tagline':r.get('tagline'),'total_cost':r.get('summary',{}).get('total_cost')} for r in routes],ensure_ascii=False)}"

    @staticmethod
    def _sse_status(s,m): return f"data: {json.dumps({'type':'status','stage':s,'message':m},ensure_ascii=False)}\n\n"
    @staticmethod
    def _sse_text(t): return f"data: {json.dumps({'type':'text','token':t},ensure_ascii=False)}\n\n"
    @staticmethod
    def _sse_message(d): return f"data: {json.dumps(d,ensure_ascii=False)}\n\n"


_STATIC_DIR = str(Path(__file__).parent / "static")
_executor = PipelineExecutor()


class SmartRouteHandler(SimpleHTTPRequestHandler):

    def __init__(self, *a, **kw):
        kw.setdefault("directory", _STATIC_DIR)
        super().__init__(*a, **kw)

    def log_message(self, f, *a):
        pass  # suppress default logging

    def do_POST(self):
        p=urlparse(self.path)
        if p.path=="/api/v1/route/plan/stream": self._handle_sse(_executor.run)
        elif p.path=="/api/v1/route/adjust/stream": self._handle_sse(_executor.run_adjust)
        else: self.send_error(404)

    def _handle_sse(self, coro_fn):
        cl=int(self.headers.get("Content-Length",0)); body=json.loads(self.rfile.read(cl))if cl>0 else{}
        query=body.get("query",""); sid=body.get("session_id",f"sess_{int(time.time())}")
        if not query: self.send_error(400); return
        self.send_response(200); self.send_header("Content-Type","text/event-stream"); self.send_header("Cache-Control","no-cache"); self.send_header("Connection","keep-alive"); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
        async def stream():
            async for line in coro_fn(query,sid): self.wfile.write(line.encode()); self.wfile.flush()
            self.wfile.write("data: [DONE]\n\n".encode()); self.wfile.flush()
        try:
            loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop); loop.run_until_complete(stream())
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception as e: traceback.print_exc()
        finally: loop.close()

    def do_OPTIONS(self):
        self.send_response(200); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS"); self.send_header("Access-Control-Allow-Headers","Content-Type"); self.end_headers()


def main():
    print(f"\n  SmartRoute Agent Server → http://localhost:8000\n  LLM: {get_settings().llm.openai_base_url}\n")
    HTTPServer(("0.0.0.0",8000),SmartRouteHandler).serve_forever()

if __name__=="__main__": main()
