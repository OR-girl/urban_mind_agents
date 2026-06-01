"""
Mock Data — 20+ real-scenario Hangzhou POIs with reviews and distance matrix.
"""
import math, random

HANGZHOU_POIS = [
    {"poi_id":"poi_xihu_001","name":"西湖","category":"景点/自然风光","lat":30.2427,"lng":120.1462,"address":"杭州市西湖区龙井路1号","avg_cost":0,"rating":4.9,"review_count":152340,"business_hours":[{"open":"00:00","close":"24:00"}],"tags":["世界遗产","免费景点","自然风光","情侣约会","家庭出游","摄影"]},
    {"poi_id":"poi_lingyin_002","name":"灵隐寺","category":"景点/寺庙","lat":30.2427,"lng":120.1060,"address":"杭州市西湖区法云弄1号","avg_cost":75,"rating":4.8,"review_count":89500,"business_hours":[{"open":"07:00","close":"17:00"}],"tags":["千年古刹","佛教文化","历史人文","祈福"]},
    {"poi_id":"poi_leifeng_003","name":"雷峰塔","category":"景点/古迹","lat":30.2315,"lng":120.1508,"address":"杭州市西湖区南山路15号","avg_cost":40,"rating":4.7,"review_count":67200,"business_hours":[{"open":"08:00","close":"20:00"}],"tags":["白蛇传说","俯瞰西湖","古迹","日落景观"]},
    {"poi_id":"poi_duanqiao_004","name":"断桥残雪","category":"景点/历史建筑","lat":30.2585,"lng":120.1572,"address":"杭州市西湖区北山街","avg_cost":0,"rating":4.6,"review_count":74100,"business_hours":[{"open":"00:00","close":"24:00"}],"tags":["西湖十景","免费景点","白蛇传","摄影"]},
    {"poi_id":"poi_suti_005","name":"苏堤","category":"景点/堤道","lat":30.2471,"lng":120.1436,"address":"杭州市西湖区苏堤","avg_cost":0,"rating":4.7,"review_count":58300,"business_hours":[{"open":"00:00","close":"24:00"}],"tags":["西湖十景","散步","骑行","春日赏花","免费"]},
    {"poi_id":"poi_santan_006","name":"三潭印月","category":"景点/岛屿","lat":30.2397,"lng":120.1503,"address":"杭州市西湖区西湖中央","avg_cost":55,"rating":4.5,"review_count":51800,"business_hours":[{"open":"08:00","close":"17:00"}],"tags":["西湖十景","人民币背景","游船","必打卡"]},
    {"poi_id":"poi_hefang_007","name":"河坊街","category":"景点/历史街区","lat":30.2429,"lng":120.1728,"address":"杭州市上城区河坊街","avg_cost":0,"rating":4.4,"review_count":42900,"business_hours":[{"open":"00:00","close":"24:00"}],"tags":["历史街区","小吃","手工艺品","夜市","免费"]},
    {"poi_id":"poi_loulou_010","name":"楼外楼","category":"餐厅/杭帮菜","lat":30.2498,"lng":120.1420,"address":"杭州市西湖区孤山路30号","avg_cost":250,"rating":4.3,"review_count":89300,"business_hours":[{"open":"11:00","close":"14:00"},{"open":"17:00","close":"21:00"}],"tags":["百年老店","杭帮菜","西湖醋鱼","龙井虾仁","商务宴请","游客必吃"]},
    {"poi_id":"poi_zhiweiguan_011","name":"知味观（湖滨总店）","category":"餐厅/杭帮菜","lat":30.2541,"lng":120.1653,"address":"杭州市上城区仁和路83号","avg_cost":120,"rating":4.5,"review_count":76200,"business_hours":[{"open":"06:30","close":"21:00"}],"tags":["百年老店","杭帮菜","小笼包","猫耳朵","早餐","家庭聚餐"]},
    {"poi_id":"poi_green_tea_012","name":"绿茶餐厅（龙井路店）","category":"餐厅/创意中餐","lat":30.2358,"lng":120.1276,"address":"杭州市西湖区龙井路83号","avg_cost":80,"rating":4.4,"review_count":61200,"business_hours":[{"open":"11:00","close":"21:30"}],"tags":["网红餐厅","环境好","性价比高","约会","年轻人","创意菜"]},
    {"poi_id":"poi_waipo_013","name":"外婆家（湖滨银泰店）","category":"餐厅/杭帮菜","lat":30.2549,"lng":120.1675,"address":"杭州市上城区延安路258号","avg_cost":65,"rating":4.3,"review_count":103400,"business_hours":[{"open":"11:00","close":"21:00"}],"tags":["高性价比","排队王","杭帮菜","红烧肉","家庭聚餐","学生党"]},
    {"poi_id":"poi_nanshan_014","name":"南山南·创意杭帮菜","category":"餐厅/创意菜","lat":30.2401,"lng":120.1602,"address":"杭州市西湖区南山路186号","avg_cost":95,"rating":4.6,"review_count":12500,"business_hours":[{"open":"11:30","close":"14:00"},{"open":"17:30","close":"21:30"}],"tags":["创意菜","小众","环境雅致","约会","新派杭帮菜","口碑好"]},
    {"poi_id":"poi_juhuayuan_015","name":"菊园面馆","category":"餐厅/面馆","lat":30.2456,"lng":120.1689,"address":"杭州市上城区中山中路368号","avg_cost":25,"rating":4.7,"review_count":8900,"business_hours":[{"open":"07:00","close":"20:00"}],"tags":["老字号","片儿川","地道","便宜","本地人推荐","快速便餐"]},
    {"poi_id":"poi_longjing_020","name":"龙井村·茶文化体验","category":"体验/茶文化","lat":30.2245,"lng":120.1189,"address":"杭州市西湖区龙井路龙井村","avg_cost":60,"rating":4.6,"review_count":24800,"business_hours":[{"open":"08:00","close":"17:00"}],"tags":["龙井茶","茶文化","自然风光","文化体验","小众"]},
    {"poi_id":"poi_huxing_021","name":"湖畔居茶楼","category":"茶楼/休闲","lat":30.2505,"lng":120.1556,"address":"杭州市西湖区湖滨路18号","avg_cost":88,"rating":4.5,"review_count":15300,"business_hours":[{"open":"09:00","close":"22:00"}],"tags":["湖景茶楼","龙井茶","下午茶","约会","安静","商务洽谈"]},
    {"poi_id":"poi_bowuguan_030","name":"浙江省博物馆（孤山馆区）","category":"景点/博物馆","lat":30.2516,"lng":120.1433,"address":"杭州市西湖区孤山路25号","avg_cost":0,"rating":4.6,"review_count":34200,"business_hours":[{"open":"09:00","close":"17:00"}],"tags":["免费","文化历史","河姆渡文化","室内","亲子","避雨避暑"]},
    {"poi_id":"poi_in77_040","name":"湖滨银泰in77","category":"购物/商场","lat":30.2550,"lng":120.1680,"address":"杭州市上城区延安路258号","avg_cost":0,"rating":4.4,"review_count":38600,"business_hours":[{"open":"10:00","close":"22:00"}],"tags":["购物中心","西湖边","餐饮集中","年轻人聚集","室内"]},
]

POI_REVIEWS = {
    "poi_loulou_010":[
        {"rating":5,"content":"西湖醋鱼必点！酸甜适中，鱼肉嫩滑，不愧是百年老店。环境在孤山脚下，窗外就是西湖，太美了。","timestamp":1748236800},
        {"rating":4,"content":"味道确实不错，就是价格偏高。龙井虾仁推荐，茶叶清香。建议提前订位，周末排队至少一小时。","timestamp":1748064000},
        {"rating":5,"content":"带父母来的，老人家很喜欢。叫花鸡和东坡肉都很好吃，服务也很到位。","timestamp":1747891200},
        {"rating":3,"content":"说实话有点失望，名不副实。菜量少，西湖醋鱼一条要200多，感觉不值。环境倒是很好。","timestamp":1747718400},
        {"rating":5,"content":"来杭州必吃的一家！虽然贵但值得。建议中午去比晚上人少点。","timestamp":1747545600},
        {"rating":2,"content":"排队排了一个半小时才吃上，上菜还慢。叫花鸡味道一般，性价比极低。","timestamp":1747372800},
        {"rating":4,"content":"环境真的绝了，孤山脚下窗外就是西湖。菜的口味偏甜，符合杭帮菜特点。","timestamp":1747200000},
        {"rating":5,"content":"第三次来了品质一直稳定。推荐定胜糕软糯香甜，龙井虾仁是招牌虾仁Q弹茶香十足。","timestamp":1747027200},
        {"rating":1,"content":"太坑了完全是游客店。菜又贵又难吃，服务态度还很差。建议大家不要去。","timestamp":1746854400},
        {"rating":4,"content":"作为杭州人偶尔招待外地朋友会来。环境好够面子，价格虽然贵但能接受。","timestamp":1746681600},
        {"rating":5,"content":"东坡肉入口即化肥而不腻。叫花鸡用荷叶包裹很香。整体体验非常好会再来的。","timestamp":1746508800},
        {"rating":3,"content":"人均250+的价格说实话没有想象中惊艳。环境加分很多，但只论味道很多小店也不差。","timestamp":1746336000},
    ],
    "poi_waipo_013":[
        {"rating":4,"content":"排队排了40分钟但是值得。红烧肉真的绝了肥瘦相间入口即化。性价比很高！","timestamp":1748236800},
        {"rating":5,"content":"三个人吃了不到200在西湖边这个地段简直不敢相信。推荐茶香鸡很嫩很入味。","timestamp":1748064000},
        {"rating":4,"content":"排队太夸张了取了号等了快一小时。但味道确实不错就是环境有点吵。","timestamp":1747891200},
        {"rating":3,"content":"感觉现在外婆家没以前好了菜的品质有所下降。但还是比一般餐厅强毕竟便宜。","timestamp":1747718400},
        {"rating":5,"content":"来杭州玩的第一顿朋友强烈推荐的。宋嫂鱼羹很好喝糖醋里脊外酥里嫩。","timestamp":1747545600},
        {"rating":4,"content":"经济实惠的选择适合家庭聚餐。建议早点去占位或者提前在App上排队。","timestamp":1747372800},
        {"rating":5,"content":"杭州性价比之王！人均六七十能吃得很饱很满足。青椒擂皮蛋和龙井虾仁都推荐。","timestamp":1747200000},
        {"rating":2,"content":"上菜速度太慢了催了好几次。红烧肉口味偏甜不太习惯杭州口味。","timestamp":1747027200},
        {"rating":4,"content":"每次来杭州都吃外婆家品质稳定价格实惠。就是每次都要排队生意太好了。","timestamp":1746854400},
        {"rating":5,"content":"绿茶饼好好吃！还有那个招牌的茶香鸡又嫩又香。三个人才180块太划算了。","timestamp":1746681600},
    ],
    "poi_nanshan_014":[
        {"rating":5,"content":"环境太好了！在南山路上一栋小洋楼里窗外就是梧桐树。菜品精致的像艺术品口味也很惊艳。","timestamp":1748236800},
        {"rating":5,"content":"带女朋友来过纪念日选了这家。氛围很适合约会灯光暧昧菜品颜值都很高。人均100出头值得。","timestamp":1748064000},
        {"rating":4,"content":"黄油脆皮鲈鱼是招牌皮脆肉嫩。南瓜浓汤也很好喝。就是位置有点隐蔽不太好找。","timestamp":1747891200},
        {"rating":3,"content":"环境不错但量真的太少了男生可能吃不饱。适合约会打卡不太适合正经吃饭。","timestamp":1747718400},
        {"rating":5,"content":"南山路上最喜欢的一家每次来杭州都来。菜色创新但不过分好吃又好看。推荐松露虾饺。","timestamp":1747545600},
        {"rating":4,"content":"小而美的餐厅座位不多建议提前订。服务很好每个菜都会介绍。整体体验不错。","timestamp":1747372800},
        {"rating":5,"content":"惊喜！每一道菜都好吃。尤其那道桂花山药绵软清甜外面裹了一层薄薄的脆壳。","timestamp":1747200000},
        {"rating":2,"content":"期望太高有点失望。主菜味道一般前菜反而更好吃。上菜间隔太长等了快20分钟。","timestamp":1747027200},
    ],
    "poi_juhuayuan_015":[
        {"rating":5,"content":"杭州最好吃的片儿川！汤头鲜得很面条劲道笋片和雪菜的量也足。本地人强烈推荐！","timestamp":1748236800},
        {"rating":5,"content":"开了几十年的老店藏在巷子里不是本地人根本找不到。一碗片儿川才18块太良心了。","timestamp":1748064000},
        {"rating":4,"content":"面很好吃环境就是老派面馆的感觉。高峰时段要等位建议避开午饭时间。","timestamp":1747891200},
        {"rating":5,"content":"秒杀那些网红面馆！片儿川的汤底能喝出来是真的熬了很久的高汤不是调料包的味道。","timestamp":1747718400},
        {"rating":4,"content":"慕名而来没让我失望。腰花面也不错处理得很干净没有异味。人均二十几块物超所值。","timestamp":1747545600},
        {"rating":3,"content":"味道还行但环境太差了。夏天没空调吃得一身汗。打包带走可能更好。","timestamp":1747372800},
    ],
    "poi_green_tea_012":[
        {"rating":5,"content":"龙井路这家环境超棒！坐落在茶园旁边空气清新。面包诱惑必点外脆里软。","timestamp":1748236800},
        {"rating":4,"content":"网红餐厅装修很有江南韵味。烤肉串和火焰虾不错价格也很亲民。","timestamp":1748064000},
        {"rating":4,"content":"排队半小时还可以接受。面包诱惑确实好吃但感觉没大家说的那么神。环境加分。","timestamp":1747891200},
        {"rating":3,"content":"感觉就是造型好看口味一般。适合拍照打卡如果是为了吃饭有更好的选择。","timestamp":1747718400},
        {"rating":5,"content":"龙井店的view太好了！坐在窗边能看到茶园。菜品性价比很高人均80吃得很饱。","timestamp":1747545600},
        {"rating":4,"content":"绿茶烤鸡是招牌外皮酥脆肉汁丰富。麻婆豆腐也做得不错很下饭。","timestamp":1747372800},
    ],
    "poi_zhiweiguan_011":[
        {"rating":5,"content":"来杭州必吃知味观！小笼包皮薄汤多猫耳朵Q弹。一楼的点心柜台也值得逛。","timestamp":1748236800},
        {"rating":4,"content":"老字号就是不一样点心品种丰富价格合理。片儿川做得也很地道。","timestamp":1748064000},
        {"rating":5,"content":"早茶推荐这里！虾肉小笼鲜肉月饼都是一绝。环境就是老派酒楼的样子很有年代感。","timestamp":1747891200},
        {"rating":3,"content":"周末人太多了跟菜市场一样吵。点心味道不错但等了将近半小时才上齐。","timestamp":1747718400},
        {"rating":4,"content":"猫耳朵很特别有点像小馄饨但更精致。叫花童子鸡也做得不错肉质鲜嫩。","timestamp":1747545600},
        {"rating":5,"content":"从小吃到大的老字号品质一直没变。每次回杭州都要来吃一次。推荐定胜糕和酥油饼！","timestamp":1747372800},
    ],
    "poi_xihu_001":[
        {"rating":5,"content":"人间天堂名不虚传！晴天时湖光山色美不胜收雨天则烟雨朦胧别有韵味。","timestamp":1748236800},
        {"rating":5,"content":"无论去多少次都不会腻的地方。建议早起去看日出湖面金光闪闪太美了。","timestamp":1748064000},
        {"rating":4,"content":"西湖很大建议租自行车或者坐电瓶车走路太累了。周末人非常多。","timestamp":1747891200},
        {"rating":5,"content":"春天来最美苏堤桃红柳绿。上次带爸妈来他们开心得不得了。免费景点太良心了。","timestamp":1747718400},
        {"rating":4,"content":"西湖很美但是人太多了。建议去西里湖那边相对安静。傍晚的夕阳特别好看。","timestamp":1747545600},
        {"rating":5,"content":"作为杭州人每天最大的幸福就是在西湖边散步。不同季节不同天气都有不同的美。","timestamp":1747372800},
    ],
    "poi_lingyin_002":[
        {"rating":5,"content":"千年古刹香火很旺。飞来峰的摩崖石刻很震撼值得细细品味。建议早点去避开人流。","timestamp":1748236800},
        {"rating":4,"content":"灵隐寺很灵验每次来杭州都会过来拜拜。门票75包含三道香。里面很大可以逛半天。","timestamp":1748064000},
        {"rating":5,"content":"飞来峰+灵隐寺的组合太棒了。石刻佛像精美绝伦寺庙庄严肃穆。一定要去！","timestamp":1747891200},
        {"rating":3,"content":"商业化有点严重到处是卖纪念品的。节假日人山人海体验感下降很多。","timestamp":1747718400},
        {"rating":4,"content":"济公殿很有意思。整个景区很大建议留3-4小时。门口的素面馆也不错。","timestamp":1747545600},
        {"rating":5,"content":"灵隐寺在飞来峰里面进飞来峰45进灵隐寺另收30。绝对值回票价佛教文化氛围浓厚。","timestamp":1747372800},
        {"rating":2,"content":"人太多了完全没法好好逛。商业化气息太浓感觉不是寺庙是景区。门票也不便宜。","timestamp":1747200000},
    ],
    "poi_longjing_020":[
        {"rating":5,"content":"龙井村太适合周末来了。沿着茶山小路走满眼绿色空气里都是茶香。","timestamp":1748236800},
        {"rating":5,"content":"在茶农家里喝到了正宗的明前龙井一杯下去满口回甘。买了一些带回家比市区便宜很多。","timestamp":1748064000},
        {"rating":4,"content":"风景很美但上山的路比较陡。不建议带腿脚不便的老人来。茶农家的农家菜也不错。","timestamp":1747891200},
        {"rating":5,"content":"小众但非常值得来！比西湖边安静多了。在茶山间漫步然后找个农家喝杯茶太惬意了。","timestamp":1747718400},
        {"rating":4,"content":"龙井村有很多茶农会拉客去家里喝茶买茶。建议找村委会推荐的几家比较靠谱。","timestamp":1747545600},
        {"rating":3,"content":"风景不错但交通不便。开车上山的路很窄周末堵车严重。公交车班次也很少。","timestamp":1747372800},
    ],
    "poi_huxing_021":[
        {"rating":5,"content":"坐在窗边喝茶窗外就是西湖人生一大享受。龙井茶很正宗茶点也精致。","timestamp":1748236800},
        {"rating":4,"content":"环境很好适合和朋友坐下来慢慢聊天。茶的价格略贵但考虑到位置可以接受。","timestamp":1748064000},
        {"rating":5,"content":"下午茶的好去处！点了一壶龙井配上桂花糕在窗边坐了一个下午看着西湖的船来来往往。","timestamp":1747891200},
        {"rating":3,"content":"周末人太多了完全感受不到茶楼的宁静。服务和出品也因此打了折扣。","timestamp":1747718400},
        {"rating":5,"content":"约会圣地！环境雅致茶香四溢窗外是西湖美景。女朋友很喜欢满分！","timestamp":1747545600},
    ],
    "poi_hefang_007":[
        {"rating":4,"content":"很有特色的老街各种小吃和手工艺品。晚上很热闹适合逛吃逛吃。","timestamp":1748236800},
        {"rating":4,"content":"游客比较多但确实有老杭州的味道。定胜糕和葱包烩都很好吃。建议傍晚来。","timestamp":1748064000},
        {"rating":3,"content":"商业化太严重了到处都是千篇一律的旅游纪念品。小吃倒是还不错。","timestamp":1747891200},
        {"rating":5,"content":"很喜欢逛河坊街！每次来杭州都来。胡庆余堂的中药博物馆也在这里免费参观很有意思。","timestamp":1747718400},
        {"rating":4,"content":"夜市氛围很好可以一路逛一路吃。就是人太多了注意财物安全。","timestamp":1747545600},
    ],
}

# Distance matrix between POIs (walking minutes)
_DISTANCE_POI_IDS = [p["poi_id"] for p in HANGZHOU_POIS]
_poi_coords = {p["poi_id"]: (p["lat"], p["lng"]) for p in HANGZHOU_POIS}

def _haversine(lat1, lng1, lat2, lng2):
    R = 6371; dlat=math.radians(lat2-lat1); dlng=math.radians(lng2-lng1)
    a=math.sin(dlat/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
    return R*2*math.atan2(math.sqrt(a),math.sqrt(1-a))

DISTANCE_MATRIX = {}
_rng = random.Random(42)
for src_id in _DISTANCE_POI_IDS:
    DISTANCE_MATRIX[src_id] = {}
    for dst_id in _DISTANCE_POI_IDS:
        if src_id == dst_id: DISTANCE_MATRIX[src_id][dst_id] = 0
        else:
            sc = _poi_coords.get(src_id,(30.25,120.15)); dc = _poi_coords.get(dst_id,(30.25,120.15))
            dkm = _haversine(*sc,*dc); wm = int(dkm/5*60*(0.9+0.2*_rng.random()))
            DISTANCE_MATRIX[src_id][dst_id] = max(1,wm)

def get_poi_by_id(poi_id: str):
    for p in HANGZHOU_POIS:
        if p["poi_id"]==poi_id: return p
    return None

def get_reviews_for_poi(poi_id: str):
    return POI_REVIEWS.get(poi_id, [
        {"rating":4,"content":"还不错的地方值得一游。","timestamp":1748236800},
        {"rating":4,"content":"体验挺好的推荐。","timestamp":1748064000},
        {"rating":3,"content":"一般般吧没有特别出彩。","timestamp":1747891200},
    ])
