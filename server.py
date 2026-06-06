#!/usr/bin/env python3
"""SmartRoute Agent — Web Server. Usage: python server.py → http://localhost:8000"""
from __future__ import annotations
import asyncio, json, sys, time, traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server — handles concurrent requests."""
    daemon_threads = True
from urllib.parse import urlparse

from smartroute.core.config import get_settings
from smartroute.mock.services import MockServiceLayer
from smartroute.schemas.state import SystemState


class PipelineExecutor:
    def __init__(self): self.mock = MockServiceLayer()

    def _classify_request(self, query: str, dialog_history: list) -> str:
        """分类请求类型"""
        if not dialog_history:
            return "NEW"

        q = query.lower()
        if any(kw in q for kw in ["换成", "换一个", "换掉", "替换", "不要这个", "换家"]):
            return "MODIFY_POI"
        if any(kw in q for kw in ["早点", "晚点", "提前", "延后", "缩短", "延长", "时间"]):
            return "MODIFY_TIME"
        if any(kw in q for kw in ["想去", "想吃", "喜欢", "不想要", "去掉", "加一个", "再加"]):
            return "MODIFY_PREFER"
        if any(kw in q for kw in ["重新", "换地方", "不去了", "换个城市", "换个区域", "重来"]):
            return "REDO"

        return "NEW"

    async def run(self, query: str, session_id: str):
        # 1. 加载已有 session
        existing = await self.mock.load_session(session_id) or {}
        dialog_history = existing.get("dialog_history", [])

        # 2. 分类请求类型
        request_type = self._classify_request(query, dialog_history)

        # 3. 构建状态（保留对话历史）
        state = SystemState(
            session_id=session_id,
            trace_id=f"trace_{session_id}",
            request_type=request_type,
            raw_query=query,
            dialog_history=dialog_history
        )

        # 4. 如果是 MODIFY 请求，合并已有状态
        if request_type != "NEW" and existing:
            state.intent = existing.get("intent")
            state.candidates = existing.get("candidates")
            state.enriched_pois = existing.get("enriched_pois")
            state.routes = existing.get("routes")

        total_start = time.time()

        # Stage 1: Intent
        yield self._sse_status("intent", "正在理解您的需求...")
        intent_success = False

        if request_type in ("NEW", "REDO", "MODIFY_PREFER"):
            try:
                from smartroute.agents.intent import IntentAgent
                agent = IntentAgent()
                result = await agent.execute(state)
                state.intent = result.get("intent")
                state.clarification_needed = result.get("clarification_needed", False)
                if not state.clarification_needed:
                    intent_success = True
            except Exception as e:
                print(f"[Intent Agent Error] {e}")
                import traceback
                traceback.print_exc()
            if not intent_success or state.clarification_needed:
                state.intent = self._fallback_intent(query)
                state.clarification_needed = False
        # MODIFY_POI 和 MODIFY_TIME 复用已有 intent

        intent = state.get_intent()
        if intent:
            yield self._sse_status("intent", f"识别意图: {intent.intent_type.value} | 城市: {intent.spatial.city}")
            yield self._sse_message({"type": "intent", "intent": state.intent})
        else:
            # 如果 intent 仍然为空，使用兜底
            state.intent = self._fallback_intent(query)
            intent = state.get_intent()
            yield self._sse_status("intent", f"使用默认意图: {intent.intent_type.value} | 城市: {intent.spatial.city}")

        # Stage 2: Retrieval
        if request_type in ("NEW", "REDO", "MODIFY_POI", "MODIFY_PREFER"):
            yield self._sse_status("retrieval", "正在搜索 POI 候选集...")
            candidates = self.mock.retrieve_candidates(intent, top_k=15) if intent else []
            state.candidates = candidates
            yield self._sse_status("retrieval", f"召回 {len(candidates)} 个候选 POI")
            yield self._sse_message({"type": "candidates", "candidates": candidates[:12]})

        # Stage 3: UGC
        if request_type in ("NEW", "REDO", "MODIFY_POI", "MODIFY_PREFER"):
            yield self._sse_status("ugc", "DeepSeek + NLP 双通道分析评论...")
            enriched = await self._run_ugc(state.candidates or [])
            state.enriched_pois = enriched
            yield self._sse_status("ugc", f"完成 {len(enriched)} 个 POI 洞察分析")
            yield self._sse_message({"type": "insights", "enriched_pois": enriched})

        # Stage 4: Route
        yield self._sse_status("route", "多约束优化求解路线...")
        enriched = state.enriched_pois or []
        if request_type == "MODIFY_POI":
            routes = self._build_routes_adjusted(enriched, query)
        elif request_type == "MODIFY_TIME":
            routes = self._build_routes_time_adjusted(enriched, query, state.routes or [])
        else:
            routes = self._build_routes(enriched)
        state.routes = routes
        yield self._sse_status("route", f"生成 {len(routes)} 套差异化方案")

        # Stage 5: Presentation
        yield self._sse_status("presentation", "生成个性化方案...")
        final = await self._run_presentation(routes, enriched, intent)
        meta_plans = [{"plan_id": r.get("plan_id"), "name": r.get("name"), "tagline": r.get("tagline"), "summary": r.get("summary", {})} for r in routes]
        yield self._sse_message({"type": "structured_meta", "plans": meta_plans, "session_id": session_id, "summary": final.get("summary", "")})

        # 非流式输出 - 直接使用 call 而不是 stream
        stream_prompt = self._build_stream_prompt(routes)
        try:
            from smartroute.services.llm.router import LLMRouter
            router = LLMRouter()
            text = await router.call(messages=[{"role": "user", "content": stream_prompt}], temperature=0.7, max_tokens=800)
            if text:
                yield self._sse_text(text)
        except Exception as e:
            print(f"[LLM Error] {e}")
            import traceback
            traceback.print_exc()
            yield self._sse_text(final.get("summary", ""))

        yield self._sse_message({"type": "structured", "plans": routes, "session_id": session_id, "plan_comparison": final.get("plan_comparison", {}), "adjustable_hints": final.get("adjustable_hints", [])})
        yield self._sse_status("presentation", f"规划完成，总耗时 {round(time.time()-total_start,1)}s")

        # 保存 session
        state.dialog_history.append({"role": "user", "content": query})
        state.dialog_history.append({"role": "assistant", "content": final.get("summary", "")})
        await self.mock.save_session(session_id, {
            "intent": state.intent,
            "candidates": state.candidates,
            "enriched_pois": state.enriched_pois,
            "routes": state.routes,
            "dialog_history": state.dialog_history
        })

    async def run_adjust(self, query: str, session_id: str):
        """Multi-turn adjustment with DeepSeek intent parsing + constraint modification."""
        yield self._sse_status("intent", "分析调整需求...")

        existing = await self.mock.load_session(session_id) or {}
        prev_routes = existing.get("routes", [])
        prev_intent = existing.get("intent")
        prev_enriched = existing.get("enriched_pois", [])
        dialog_history = existing.get("dialog_history", [])

        if not prev_routes:
            # No previous plan — fall back to fresh planning
            async for line in self.run(query, session_id):
                yield line
            return

        # Parse adjustment intent with DeepSeek
        adjust = await self._parse_adjust_intent(query, prev_routes)
        yield self._sse_status("intent", f"调整类型: {adjust.get('type_label', '通用调整')} — {adjust.get('summary', '')}")

        # Apply adjustment to previous intent
        state = SystemState(session_id=session_id, trace_id=f"trace_{session_id}",
                            request_type="MODIFY", raw_query=query, dialog_history=dialog_history)
        if prev_intent:
            state.intent = prev_intent

        # Modify constraints based on adjustment type
        intent_obj = state.get_intent()
        if intent_obj and adjust.get("constraint_mods"):
            state.intent = self._apply_constraint_mods(intent_obj, adjust["constraint_mods"])

        # Override: if user says "想去X" and X is a known POI, force it into the plan
        _poi_name_from_query = self._extract_poi_name(query)
        if _poi_name_from_query:
            adjust["type"] = "add_specific_poi"
            adjust["type_label"] = "添加指定POI"
            adjust["summary"] = f"加入「{_poi_name_from_query}」"
            adjust["response_text"] = f"好的，已将「{_poi_name_from_query}」加入路线"
            adjust.setdefault("constraint_mods", {})
            adjust["constraint_mods"]["add_poi_name"] = _poi_name_from_query

        # Re-retrieve with modified constraints
        yield self._sse_status("retrieval", "根据新约束重新匹配 POI...")
        candidates = self.mock.retrieve_candidates(state.get_intent(), top_k=15) if state.get_intent() else []
        state.candidates = candidates
        yield self._sse_status("retrieval", f"召回 {len(candidates)} 个候选 POI")

        # UGC on new candidates
        enriched = await self._run_ugc(candidates)
        state.enriched_pois = enriched
        yield self._sse_status("ugc", f"完成 {len(enriched)} 个 POI")

        # Build adjusted routes
        routes = self._build_routes_adjusted_v2(enriched, adjust, prev_routes)
        yield self._sse_status("route", f"生成 {len(routes)} 套调整方案")

        # Presentation with comparison
        final = await self._run_presentation(routes, enriched, state.get_intent())
        yield self._sse_message({"type": "structured_meta",
            "plans": [{"plan_id": r.get("plan_id"), "name": r.get("name"),
                       "tagline": r.get("tagline"), "summary": r.get("summary", {})} for r in routes],
            "session_id": session_id,
            "summary": adjust.get("response_text", f"已根据「{query}」调整方案")})

        # Stream adjustment explanation
        try:
            from smartroute.services.llm.router import LLMRouter
            async for token in LLMRouter().stream(
                messages=[{"role": "user", "content": f"用户对路线方案提出调整：「{query}」。调整内容：{adjust.get('summary', '')}。请用1-2句话友好地说明调整后的变化。"}],
                temperature=0.7, max_tokens=400):
                yield self._sse_text(token)
        except Exception:
            yield self._sse_text(adjust.get("response_text", f"已根据「{query}」重新规划。"))

        # Build before/after comparison
        comparison = self._build_adjust_comparison(prev_routes, routes, query)

        yield self._sse_message({"type": "structured", "plans": routes, "session_id": session_id,
            "plan_comparison": final.get("plan_comparison", {}),
            "adjustable_hints": final.get("adjustable_hints", []),
            "adjust_comparison": comparison})

        # Save session
        dialog_history.append({"role": "user", "content": query})
        dialog_history.append({"role": "assistant", "content": final.get("summary", "")})
        await self.mock.save_session(session_id, {
            "intent": state.intent, "candidates": candidates,
            "enriched_pois": enriched, "routes": routes,
            "dialog_history": dialog_history
        })

    async def _run_ugc(self, candidates):
        from smartroute.agents.ugc.llm_channel import get_llm_channel
        from smartroute.agents.ugc.nlp_analyzer import NLPAnalyzer
        llm_ch, nlp = get_llm_channel(), NLPAnalyzer()
        llm_pois = sorted(candidates, key=lambda p: p.get("review_count", 0), reverse=True)[:3]
        processed = {p["poi_id"] for p in llm_pois}
        enriched = []
        if llm_pois:
            sem = asyncio.Semaphore(3)
            async def _analyze_one(p):
                async with sem:
                    try:
                        return await asyncio.wait_for(
                            llm_ch.analyze(p, self.mock.get_reviews_for_poi(p["poi_id"])), timeout=35.0)
                    except Exception:
                        return nlp.analyze(p, self.mock.get_reviews_for_poi(p["poi_id"]))
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*[_analyze_one(p) for p in llm_pois], return_exceptions=True),
                    timeout=50.0)
            except asyncio.TimeoutError:
                results = [nlp.analyze(p, self.mock.get_reviews_for_poi(p["poi_id"])) for p in llm_pois]
            for p, r in zip(llm_pois, results):
                if isinstance(r, Exception):
                    r = nlp.analyze(p, self.mock.get_reviews_for_poi(p["poi_id"]))
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

    @staticmethod
    def _extract_poi_name(query: str) -> str | None:
        """Extract POI name from queries like '想去X' or '加入X'."""
        import re
        patterns = [r"想去(.+?)(?:[，,。\s]|$)", r"(?:加|加入|添加)(?:一个|个)?(.+?)(?:[，,。\s]|$)"]
        for pat in patterns:
            m = re.search(pat, query)
            if m:
                name = m.group(1).strip()
                if len(name) >= 2:
                    return name
        # Also check if the query IS just a POI name
        known = {"断桥残雪", "西湖", "灵隐寺", "雷峰塔", "苏堤", "三潭印月",
                  "河坊街", "楼外楼", "外婆家", "绿茶", "知味观", "龙井村",
                  "湖畔居", "菊园面馆", "南山南", "湖滨银泰in77", "浙江省博物馆"}
        for name in known:
            if name in query:
                return name
        return None

    def _build_routes(self, enriched):
        rst=[p for p in enriched if "餐" in p.get("category","")]; att=[p for p in enriched if "景点" in p.get("category","")]
        tea=[p for p in enriched if "茶" in p.get("category","")]; shop=[p for p in enriched if "购物" in p.get("category","")]
        oth=[p for p in enriched if p not in rst and p not in att and p not in tea and p not in shop]
        strategies=[("经典稳妥","兼顾体验与效率，适合首次到访",(att[:2] if att else[])+(rst[:1] if rst else[])+(shop[:1] if shop else[])+(tea[:1] if tea else[])+(rst[1:2] if len(rst)>1 else[])+oth[:1]),
                     ("避峰省时","规避排队高峰，时间利用率最高",sorted((att[:2] if att else[])+(rst[:2] if rst else[])+(shop[:1] if shop else[])+oth[:1],key=lambda p:p.get("review_count",10**9))),
                     ("极致体验","不惜排队，追求最佳体验",sorted((rst[:1] if rst else[])+(att[:2] if att else[])+(shop[:1] if shop else[])+(rst[1:2] if len(rst)>1 else[])+(tea[:1] if tea else[])+oth[:1],key=lambda p:p.get("rating",0),reverse=True))]
        return self._build_timelines(strategies)

    def _build_routes_adjusted(self, enriched, adjust_query):
        q=adjust_query.lower(); sorted_p=sorted(enriched,key=lambda p:p.get("avg_cost",0)or 0) if any(k in q for k in('便宜','省钱','贵','预算')) else sorted(enriched,key=lambda p:p.get("rating",0)or 0,reverse=True)
        rst=[p for p in sorted_p if "餐" in p.get("category","")]; att=[p for p in sorted_p if "景点" in p.get("category","")]
        tea=[p for p in sorted_p if "茶" in p.get("category","")]; oth=[p for p in sorted_p if p not in rst and p not in att and p not in tea]
        return self._build_timelines([(f"调整方案",f"基于「{adjust_query}」的优化路线",(att[:2] if att else[])+(rst[:2] if rst else[])+(tea[:1] if tea else[])+oth[:1])])

    def _build_routes_time_adjusted(self, enriched, adjust_query, existing_routes):
        """根据时间调整请求修改路线"""
        q = adjust_query.lower()

        # 解析时间调整意图
        start_offset = 0
        if "早点" in q or "提前" in q:
            start_offset = -60  # 提前1小时
        elif "晚点" in q or "延后" in q:
            start_offset = 60   # 延后1小时

        if not existing_routes:
            return self._build_routes(enriched)

        adjusted_routes = []
        for route in existing_routes:
            new_route = route.copy()
            new_timeline = []
            for item in route.get("timeline", []):
                new_item = item.copy()
                # 调整时间
                try:
                    arrive = item.get("arrive_time", "09:00")
                    h, m = map(int, arrive.split(":"))
                    new_h = (h + start_offset // 60) % 24
                    new_m = m + start_offset % 60
                    if new_m >= 60:
                        new_h = (new_h + 1) % 24
                        new_m -= 60
                    elif new_m < 0:
                        new_h = (new_h - 1) % 24
                        new_m += 60
                    new_item["arrive_time"] = f"{new_h:02d}:{new_m:02d}"
                except Exception:
                    pass
                new_timeline.append(new_item)

            new_route["timeline"] = new_timeline
            new_route["name"] = f"时间调整方案"
            new_route["tagline"] = f"基于「{adjust_query}」调整"
            adjusted_routes.append(new_route)

        return adjusted_routes if adjusted_routes else self._build_routes(enriched)

    # ── V2 Multi-Turn Adjustment Helpers ──────────────────────────────

    async def _parse_adjust_intent(self, query: str, prev_routes: list) -> dict:
        """Use DeepSeek to parse adjustment query into structured intent."""
        prev_summary = []
        for r in prev_routes:
            pois = [t.get("poi_name", "") for t in r.get("timeline", [])]
            prev_summary.append(f"{r.get('name', '')}: {' → '.join(pois)} (¥{r.get('summary', {}).get('total_cost', 0)}/人, {r.get('summary', {}).get('total_distance_km', 0)}km)")

        prompt = f"""你是一个路线调整助手。分析用户的调整需求，输出结构化JSON。

用户当前方案:
{chr(10).join(prev_summary)}

用户调整需求: 「{query}」

请输出JSON（仅JSON，无其他文字）:
{{"type": "replace_poi|add_category|modify_time|modify_budget|modify_constraint|general", "type_label": "中文类型标签", "summary": "一句话概括调整内容", "response_text": "对用户说的友好确认语", "constraint_mods": {{"target_poi": "要替换的POI名或null", "replace_reason": "更便宜|评分更高|排队更少|类别不同|null", "add_category": "要添加的类别或null(如下午茶、购物、博物馆)", "time_end": "新的结束时间或null(如18:00)", "time_start": "新的开始时间或null", "budget_new": 新的每人均算数字或null, "max_walk_km": 步行上限公里数或null, "avoid_poi_types": ["要排除的POI类型"], "prefer_poi_types": ["优先选择的POI类型"]}}}}"""

        try:
            from smartroute.services.llm.router import LLMRouter
            router = LLMRouter()
            result_text = await router.call(messages=[{"role": "user", "content": prompt}], temperature=0.1, max_tokens=500)
            text = (result_text or "").strip()
            for fence in ("```json", "```"):
                if fence in text:
                    s = text.find(fence) + len(fence); e = text.find("```", s)
                    if e > s:
                        text = text[s:e].strip(); break
            bs = text.find("{"); be = text.rfind("}")
            if bs >= 0 and be > bs:
                text = text[bs:be + 1]
            result = json.loads(text)
            if not result.get("type"):
                raise ValueError("No type")
            return result
        except Exception:
            return self._keyword_adjust_fallback(query)

    def _keyword_adjust_fallback(self, query: str) -> dict:
        """Keyword-based fallback when DeepSeek parsing fails."""
        q = query.lower()
        # "想去X" — extract the POI name and force-add it
        if "想去" in q:
            for prefix in ["想去"]:
                idx = q.find(prefix)
                if idx >= 0:
                    name = q[idx + len(prefix):].strip()
                    if name:
                        return {"type": "add_specific_poi", "type_label": "添加指定POI",
                                "summary": f"加入「{name}」",
                                "response_text": f"好的，已将「{name}」加入路线",
                                "constraint_mods": {"add_poi_name": name, "target_poi": "西湖"}}
        if any(k in q for k in ('购物', '商场', '逛街', '逛', '买')):
            return {"type": "add_category", "type_label": "添加购物", "summary": "加入购物地点",
                    "response_text": "好的，已在路线中加入购物地点", "constraint_mods": {"add_category": "购物"}}
        if any(k in q for k in ('加', '增加', '加入', '添')):
            return {"type": "add_category", "type_label": "添加类别", "summary": f"添加: {query}",
                    "response_text": f"好的，已在路线中加入相关内容", "constraint_mods": {"add_category": "用户指定"}}
        if any(k in q for k in ('换', '替', '改成', '不要')):
            return {"type": "replace_poi", "type_label": "替换POI", "summary": f"替换POI: {query}",
                    "response_text": f"好的，已根据「{query}」替换相关地点", "constraint_mods": {"target_poi": None, "replace_reason": "用户指定"}}
        if any(k in q for k in ('便宜', '省钱', '预算', '贵', '价格', '降')):
            return {"type": "modify_budget", "type_label": "调整预算", "summary": "降低费用",
                    "response_text": "好的，已调整为更经济的选择", "constraint_mods": {"budget_new": 80}}
        if any(k in q for k in ('时间', '提前', '延后', '结束', '5点', '6点', '7点', '8点')):
            return {"type": "modify_time", "type_label": "调整时间", "summary": "调整时间安排",
                    "response_text": "好的，已根据新时间重新安排", "constraint_mods": {}}
        return {"type": "general", "type_label": "通用调整", "summary": query,
                "response_text": f"已根据「{query}」重新规划方案", "constraint_mods": {}}

    def _apply_constraint_mods(self, intent_obj, mods: dict) -> dict:
        """Apply constraint modifications to the intent object."""
        data = intent_obj.model_dump() if hasattr(intent_obj, "model_dump") else intent_obj.copy()
        if mods.get("budget_new"):
            data.setdefault("budget", {})["per_person"] = mods["budget_new"]
            data["budget"]["level"] = "budget" if mods["budget_new"] < 80 else ("mid" if mods["budget_new"] < 200 else "premium")
        if mods.get("add_category"):
            data.setdefault("preferences", {}).setdefault("nice_to_have", []).append(mods["add_category"])
        if mods.get("avoid_poi_types"):
            existing_avoids = data.setdefault("preferences", {}).setdefault("avoid", [])
            for t in mods["avoid_poi_types"]:
                if t not in existing_avoids:
                    existing_avoids.append(t)
        if mods.get("prefer_poi_types"):
            data.setdefault("preferences", {}).setdefault("must_have", []).extend(mods["prefer_poi_types"])
        if mods.get("max_walk_km"):
            data["walk_tolerance_km"] = mods["max_walk_km"]
        return data

    def _build_routes_adjusted_v2(self, enriched: list, adjust: dict, prev_routes: list) -> list:
        """Build adjusted routes with DeepSeek-parsed intent."""
        adjust_type = adjust.get("type", "general")
        mods = adjust.get("constraint_mods", {})
        reason = mods.get("replace_reason", "") or adjust.get("summary", "")
        q_lower = adjust.get("summary", "").lower()
        prefer_cheap = ("便宜" in reason or "省钱" in reason or "便宜" in q_lower or "省钱" in q_lower or "降" in q_lower)
        prefer_rating = "评分" in reason or "好" in reason
        prefer_quiet = "排队" in reason or "少" in reason

        if prefer_cheap:
            enriched = sorted(
                [p for p in enriched if (p.get("avg_cost", 0) or 0) <= 200],
                key=lambda p: p.get("avg_cost", 0) or 0)
        elif prefer_rating:
            enriched.sort(key=lambda p: p.get("rating", 0) or 0, reverse=True)
        elif prefer_quiet:
            enriched.sort(key=lambda p: p.get("review_count", 0) or 10**9)

        if adjust_type == "replace_poi" and mods.get("target_poi"):
            target = mods["target_poi"]
            enriched = [p for p in enriched if target not in (p.get("name", "") or "")]
        if adjust_type == "modify_budget" and mods.get("budget_new"):
            cap = mods["budget_new"]
            enriched = [p for p in enriched if (p.get("avg_cost", 0) or 0) <= cap * 1.5]
            if not prefer_cheap:
                enriched.sort(key=lambda p: p.get("avg_cost", 0) or 0)

        restaurants = [p for p in enriched if "餐" in p.get("category", "")]
        attractions = [p for p in enriched if "景点" in p.get("category", "")]
        tea_shop = [p for p in enriched if "茶" in p.get("category", "")]
        shopping = [p for p in enriched if "购物" in p.get("category", "")]
        others = [p for p in enriched if p not in restaurants and p not in attractions and p not in tea_shop and p not in shopping]

        # Build base sequence
        seq = ((attractions[:2] if attractions else []) +
               (restaurants[:1] if restaurants else []) +
               (shopping[:1] if shopping else []) +
               (tea_shop[:1] if tea_shop else []) +
               (restaurants[1:2] if len(restaurants) > 1 else []) +
               others[:1])

        # "add_specific_poi" — force a named POI into the timeline
        if adjust_type == "add_specific_poi" and mods.get("add_poi_name"):
            target_name = mods["add_poi_name"]
            # Find that POI in the enriched list
            forced = [p for p in enriched if target_name in (p.get("name", "") or "")]
            if forced:
                # Remove target_poi if specified, then prepend the requested POI
                if mods.get("target_poi"):
                    seq = [p for p in seq if mods["target_poi"] not in (p.get("name", "") or "")]
                # Ensure the requested POI is the first attraction
                if forced[0] not in seq:
                    if attractions:
                        seq = [forced[0]] + [p for p in seq if p.get("category", "") != forced[0].get("category", "")]

        strategies = [
            ("调整方案", f"根据「{adjust.get('summary', '用户需求')}」优化", seq),
        ]
        if adjust_type == "add_category" and mods.get("add_category"):
            cat = mods["add_category"]
            strategies[0] = (strategies[0][0], strategies[0][1],
                             (attractions[:2] if attractions else []) +
                             (restaurants[:1] if restaurants else []) +
                             [p for p in others if cat in (p.get("category", "") or "")][:1] +
                             (tea_shop[:1] if tea_shop else []) +
                             (restaurants[1:2] if len(restaurants) > 1 else []))

        return self._build_timelines(strategies)

    def _build_adjust_comparison(self, prev_routes: list, new_routes: list, query: str) -> dict:
        """Build before/after comparison for adjustment display."""
        prev_cost = prev_routes[0].get("summary", {}).get("total_cost", 0) if prev_routes else 0
        prev_walk = prev_routes[0].get("summary", {}).get("total_distance_km", 0) if prev_routes else 0
        prev_pois = [t.get("poi_name", "") for r in prev_routes for t in r.get("timeline", [])]

        new_cost = new_routes[0].get("summary", {}).get("total_cost", 0) if new_routes else 0
        new_walk = new_routes[0].get("summary", {}).get("total_distance_km", 0) if new_routes else 0
        new_pois = [t.get("poi_name", "") for r in new_routes for t in r.get("timeline", [])]

        removed = [p for p in prev_pois if p not in new_pois]
        added = [p for p in new_pois if p not in prev_pois]

        changes = []
        if removed:
            changes.append(f"移除: {', '.join(removed)}")
        if added:
            changes.append(f"新增: {', '.join(added)}")
        if prev_cost != new_cost:
            changes.append(f"费用: ¥{prev_cost} → ¥{new_cost} ({'+' if new_cost > prev_cost else ''}{new_cost - prev_cost})")
        if abs(prev_walk - new_walk) > 0.1:
            changes.append(f"步行: {prev_walk}km → {new_walk}km")

        return {"adjust_query": query, "changes": changes, "prev_cost": prev_cost, "new_cost": new_cost,
                "prev_walk": prev_walk, "new_walk": new_walk, "removed": removed, "added": added}

    # ── Route Builder ──────────────────────────────

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
        emap = {p["poi_id"]: p for p in enriched}
        reasons = {}

        # 生成个性化推荐理由
        try:
            from smartroute.agents.presentation.reason_generator import PersonalizedReasonGenerator
            generator = PersonalizedReasonGenerator()
            for route in routes:
                for item in route.get("timeline", []):
                    poi_id = item.get("poi_id")
                    poi_data = emap.get(poi_id, {})
                    if poi_data:
                        try:
                            reason = await generator.generate(poi=poi_data, profile=None, intent=intent)
                            reasons[poi_id] = reason
                        except Exception:
                            reasons[poi_id] = f"{item.get('poi_name', '')}，值得一游"
        except Exception as e:
            print(f"[Presentation Error] {e}")

        for r in routes:
            for item in r.get("timeline", []):
                item["why_for_you"] = reasons.get(item.get("poi_id"), f"{item.get('poi_name', '')}，值得一游")

        names = " / ".join(r["name"] for r in routes)
        costs = [r.get("summary", {}).get("total_cost", 0) or 0 for r in routes]
        mc = min(costs) if costs else 0
        scene = intent.intent_type.value if intent else "出行"

        from smartroute.agents.presentation.comparison import PlanComparisonGenerator
        from smartroute.agents.presentation.hints import AdjustableHintsGenerator

        return {
            "summary": f"为您定制了 {len(routes)} 套{scene}方案：{names}，最低 ¥{mc}/人",
            "plan_comparison": PlanComparisonGenerator().generate(routes),
            "adjustable_hints": AdjustableHintsGenerator().generate(routes, emap)
        }

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
    ThreadingHTTPServer(("0.0.0.0",8000),SmartRouteHandler).serve_forever()

if __name__=="__main__": main()
