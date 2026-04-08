import { motion } from 'framer-motion'
import useDailyTaskStore from '@/store/useDailyTaskStore'

interface InspirationDailyProps {
  className?: string
  onTear?: () => void
}

interface DailyContent {
  headline: string
  body: string
  illustration: string
  weather: string
  weatherEmoji: string
  miniAd: string
}

const DAILY_CONTENT: DailyContent[] = [
  { headline: '会飞的鱼被发现了！', body: '本报讯——南太平洋传来惊人消息：一群彩色飞鱼昨日飞越了整座小岛。目击者称，它们的翅膀上画满了彩虹。科学家呼吁全球小画家赶紧把它画下来，作为珍贵的科学记录。', illustration: '🐟✨', weather: '晴转棉花糖', weatherEmoji: '☀️', miniAd: '🖍️ 彩虹蜡笔第二盒半价' },
  { headline: '棉花糖云朵来袭！', body: '本报讯——气象局发布甜蜜警报：受暖气流影响，今日全市云朵将变为棉花糖材质。建议市民携带长竹竿出门采集。草莓味较稀有，先到先得。', illustration: '☁️🍬', weather: '多云转甜', weatherEmoji: '☁️', miniAd: '🎒 飞行书包预售中' },
  { headline: '海底城堡首次开放', body: '本报讯——美人鱼女王今日签署法令，向陆地儿童开放海底水晶宫参观。入场条件：提交一幅你心目中海底城堡的设计图。最佳作品将被建成真正的珊瑚雕塑。', illustration: '🏰🌊', weather: '海风轻拂', weatherEmoji: '🌊', miniAd: '🫧 防水画纸新到货' },
  { headline: '恐龙厨师遇到难题', body: '本报讯——自然历史博物馆证实：一只复活的霸王龙已成功通过厨师资格考试，但因手臂太短无法翻锅。它正在全球征集解决方案，最实用的发明将获颁"最佳恐龙助手"奖章。', illustration: '🦕👨‍🍳', weather: '局部火山灰', weatherEmoji: '🌋', miniAd: '📏 恐龙手臂加长器热销' },
  { headline: '星星列车即将发车', body: '本报讯——银河铁路公司宣布：开往北极星的特快列车将于今晚发车。列车由108节星光车厢组成，沿途停靠月球站和火星站。购票方式：画一幅最酷的火车交给站长。', illustration: '🚂⭐', weather: '满天星斗', weatherEmoji: '🌙', miniAd: '🔭 迷你望远镜买一送一' },
  { headline: '宠物时装周开幕', body: '本报讯——第三届全球宠物时装周今日在中央公园隆重开幕。本届主题为"超级英雄"，所有参赛宠物须身着小主人亲手设计的披风。冠军奖品：一年份的小鱼干。', illustration: '🦸‍♀️🐕', weather: '适宜走秀', weatherEmoji: '✨', miniAd: '🧵 宠物披风DIY套装' },
  { headline: '彩虹滑梯破世界纪录', body: '本报讯——工程师团队宣布，从彩虹最高点到棉花糖池塘的超级滑梯已竣工，全长7.7公里，创下吉尼斯世界纪录。试滑员表示：屁股有点烫，但非常值得。', illustration: '🌈🎢', weather: '七彩阵雨', weatherEmoji: '🌈', miniAd: '🩳 防烫滑梯裤限量发售' },
  { headline: '魔法棒突发故障', body: '本报讯——魔法学院发布紧急通告：巫师爷爷的百年魔法棒出现罕见故障，目前只能将纸上的画变为实物。学院建议小朋友们谨慎作画——上次有人画了一只霸王龙，场面一度混乱。', illustration: '🪄✨', weather: '偶有魔法闪电', weatherEmoji: '⚡', miniAd: '📒 防魔法画纸上新' },
  { headline: '月球游乐场盛大开业', body: '本报讯——经过三年建设，月球欢乐谷今日正式开业。由于引力仅为地球六分之一，跳一下可飞三米，摩天轮转一圈需要半小时。园方提醒：请系好安全带，不要飞太高。', illustration: '🌙🎠', weather: '月球：零重力晴', weatherEmoji: '🌙', miniAd: '🧑‍🚀 太空旅行险仅9.9元' },
  { headline: '猫咪帽子设计大赛', body: '本报讯——全球猫咪联合会宣布举办首届帽子设计大赛。评委由三只资深布偶猫担任，评分标准：可爱度占60%，实用度占20%，猫粮贿赂度占20%。投稿截止日期：明天。', illustration: '🐱🎩', weather: '有猫毛飘落', weatherEmoji: '🐱', miniAd: '🧶 猫咪毛线球特惠' },
  { headline: '糖果屋紧急修缮通知', body: '本报讯——童话镇建设局发布公告：三号街的糖果屋巧克力大门因高温融化，目前使用临时饼干门替代。急需一位小建筑师提交新设计方案，要求：好看、好吃、不怕热。', illustration: '🍭🏠', weather: '高温融巧克力', weatherEmoji: '🌡️', miniAd: '🍫 耐热巧克力砖发明' },
  { headline: '小龙搬家引热议', body: '本报讯——一条三岁小火龙决定从冰山搬到火山旁边，理由是"想住暖和点"。邻居们担心它打喷嚏会引发火灾，建议它先学会控制火焰。小龙表示会努力练习。', illustration: '🐉🏡', weather: '局部喷火', weatherEmoji: '🔥', miniAd: '🧯 防火窗帘打折中' },
  { headline: '果汁海洋震惊科学界', body: '本报讯——海洋研究所证实：北冰洋一片区域的海水已变为鲜榨橙汁。科学家推测与海底的巨型橙子矿脉有关。沿岸居民表示早餐方便多了，但鱼的意见很大。', illustration: '🧃🏊', weather: '有橙汁阵雨', weatherEmoji: '🍊', miniAd: '🥤 海洋橙汁瓶装版' },
  { headline: '企鹅溜冰赛冠军出炉', body: '本报讯——南极冬季溜冰锦标赛落幕，穿粉色溜冰鞋的帝企鹅小粉以完美的三周半跳夺冠。赛后它表示获胜秘诀是：每天吃十条鱼保持体力。', illustration: '🐧⛸️', weather: '零下40°适宜溜冰', weatherEmoji: '❄️', miniAd: '⛸️ 企鹅同款溜冰鞋' },
  { headline: '空中花园惊现市区', body: '本报讯——今晨六点，市中心一座花园缓缓升空，目前悬停在200米高处。园丁大叔淡定表示，是昨晚浇了太多魔法肥料。居民们改乘热气球去散步。', illustration: '🌺☁️', weather: '漂浮花粉', weatherEmoji: '🌸', miniAd: '🎈 私人热气球月租优惠' },
  { headline: '青蛙国王加冕典礼', body: '本报讯——荷花池塘举行了盛大的国王加冕仪式。新任蛙王在就职演说中承诺：让每只青蛙都住上带阳台的荷叶。但王冠还没做好，急需一位小设计师帮忙！', illustration: '🐸👑', weather: '池塘微风', weatherEmoji: '🍃', miniAd: '👑 纯金小王冠代工' },
  { headline: '树精灵招室友启事', body: '本报讯——住在千年橡树里的小精灵贴出招室友告示，要求：会画画、爱讲故事、不打呼噜。月租：三颗橡果。精灵表示上一任室友是只啄木鸟，"太吵了"。', illustration: '🧚‍♂️🌳', weather: '森林有薄雾', weatherEmoji: '🌲', miniAd: '🏡 树屋装修找我们' },
  { headline: '变色森林之谜破解', body: '本报讯——植物学家经过三年研究终于发现：神秘变色森林的秘密是一群调皮的变色龙在树上玩捉迷藏时把颜色蹭到了树干上。林业局表示不打算制止，因为太好看了。', illustration: '🌲🎨', weather: '五彩缤纷', weatherEmoji: '🎨', miniAd: '🎨 森林写生团报名中' },
  { headline: '音符桥通车典礼举行', body: '本报讯——历时两年建造的音符桥今日通车。行人每踩一步都会发出一个音符，快跑是摇滚乐，慢走是古典乐。桥管处提醒：禁止在桥上跳踢踏舞，上周差点塌了。', illustration: '🎶🌉', weather: '有旋律微风', weatherEmoji: '🎵', miniAd: '🎹 随身钢琴键盘特价' },
  { headline: '太阳正式申请墨镜', body: '本报讯——太阳今日向宇宙管理局提交申请："本星工作38亿年，从未配发护目设备，强烈要求一副合适的墨镜。"局方表示正在全球征集设计方案。', illustration: '☀️😎', weather: '超级晴（太阳在抱怨）', weatherEmoji: '☀️', miniAd: '🕶️ 巨型墨镜定制服务' },
  { headline: '棒棒糖树大丰收', body: '本报讯——魔法农场迎来棒棒糖树大丰收，今年产量是去年的三倍。草莓味最受欢迎，彩虹味最稀有。农场主提醒采摘者：吃之前请洗手，树上有魔法糖粉。', illustration: '🍭🌴', weather: '甜度超标', weatherEmoji: '🍬', miniAd: '🪣 棒棒糖采摘篮上新' },
]

function getDailyContent(): DailyContent {
  const now = new Date()
  const start = new Date(now.getFullYear(), 0, 0)
  const dayOfYear = Math.floor((now.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
  return DAILY_CONTENT[dayOfYear % DAILY_CONTENT.length]
}

function formatDate(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const weekdays = ['日', '一', '二', '三', '四', '五', '六']
  return `${year}年${month}月${day}日 星期${weekdays[now.getDay()]}`
}

function getEditionNumber(): number {
  const launch = new Date(2026, 0, 1)
  return Math.floor((Date.now() - launch.getTime()) / (1000 * 60 * 60 * 24)) + 1
}

const serif = '"Noto Serif SC", "Source Han Serif CN", "Songti SC", STSong, serif'

export default function InspirationDaily({ className = '', onTear }: InspirationDailyProps) {
  const canClaim = useDailyTaskStore((s) => s.canClaimToday())
  const content = getDailyContent()
  const dateStr = formatDate()
  const edition = getEditionNumber()

  const muted = !canClaim

  return (
    <div
      className={`relative overflow-hidden rounded-card ${
        muted ? 'opacity-60' : ''
      } ${className}`}
      style={{
        background: muted ? '#eae7e1' : '#FDF8F0',
        color: muted ? '#999' : '#2a2a2a',
      }}
    >
      {/* Subtle paper grain */}
      {!muted && (
        <div
          className="absolute inset-0 pointer-events-none opacity-[0.035]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='200' height='200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)'/%3E%3C/svg%3E")`,
          }}
        />
      )}

      {/* =========== MASTHEAD — tear zone =========== */}
      <div
        className="relative select-none"
        onClick={canClaim ? onTear : undefined}
        style={canClaim ? { cursor: 'grab' } : undefined}
      >
        {/* Thick top rule */}
        <div className={`h-[3px] ${muted ? 'bg-gray-300' : 'bg-gray-900'}`} />
        <div className={`h-[1px] mt-[2px] mx-3 ${muted ? 'bg-gray-200' : 'bg-gray-900/40'}`} />

        <div className="px-4 pt-2 pb-1 text-center">
          {/* Date row */}
          <div className="flex items-center justify-between" style={{ fontSize: 9, fontFamily: serif }}>
            <span>第 {edition} 期</span>
            <span>{dateStr}</span>
            <span>每日一份 · 免费领取</span>
          </div>

          {/* Thin rule */}
          <div className={`border-t my-1.5 ${muted ? 'border-gray-200' : 'border-gray-900/20'}`} />

          {/* Nameplate */}
          <h3
            className="text-3xl sm:text-4xl font-black tracking-[0.4em] leading-none py-1"
            style={{ fontFamily: serif }}
          >
            灵感日报
          </h3>

          {/* English subtitle */}
          <p
            className="text-[8px] sm:text-[9px] tracking-[0.35em] uppercase mt-0.5"
            style={{ opacity: muted ? 0.4 : 0.35, fontFamily: serif }}
          >
            The Inspiration Daily · For Young Creators
          </p>

          {/* Double rule */}
          <div className="mt-2 mb-1">
            <div className={`border-t-[2.5px] ${muted ? 'border-gray-300' : 'border-gray-900'}`} />
            <div className={`border-t mt-[2px] ${muted ? 'border-gray-200' : 'border-gray-900/50'}`} />
          </div>
        </div>

        {/* Tear hint */}
        {canClaim && (
          <div className="relative h-6 flex items-center px-4">
            <div className="flex-1 border-t-2 border-dashed border-primary/25" />
            <motion.span
              className="absolute right-4 flex items-center gap-1 text-[10px] text-primary/50"
              animate={{ x: [0, 6, 0] }}
              transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
            >
              ✂️ 撕开领星星
            </motion.span>
          </div>
        )}
      </div>

      {/* =========== CONTENT AREA =========== */}
      {canClaim ? (
        <div className="px-4 pb-3">
          {/* --- Headline banner --- */}
          <div className="flex gap-3 items-start">
            {/* Main headline + body */}
            <div className="flex-1 min-w-0">
              <h4
                className="text-lg sm:text-xl font-bold leading-tight"
                style={{ fontFamily: serif }}
              >
                {content.headline}
              </h4>
              <div className={`border-t my-1.5 border-gray-900/10`} />
              <p
                className="text-xs sm:text-sm leading-relaxed text-gray-700"
                style={{ fontFamily: serif, textAlign: 'justify' }}
              >
                <span className="text-2xl font-bold float-left mr-1 leading-[1] text-primary/80"
                  style={{ fontFamily: serif }}
                >
                  {content.body[0]}
                </span>
                {content.body.slice(1)}
              </p>
            </div>

            {/* Illustration column with vertical rule */}
            <div className="flex-shrink-0 flex items-stretch">
              <div className={`w-px self-stretch bg-gray-900/10 mr-2.5`} />
              <div className="flex flex-col items-center justify-center w-14 sm:w-16">
                <motion.span
                  className="text-4xl sm:text-5xl block"
                  animate={{ y: [0, -3, 0] }}
                  transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                >
                  {content.illustration}
                </motion.span>
              </div>
            </div>
          </div>

          {/* --- Bottom row: weather + mini-ad --- */}
          <div className="mt-2.5">
            <div className={`border-t border-gray-900/10 mb-2`} />
            <div className="flex items-center justify-between text-[10px]" style={{ fontFamily: serif }}>
              {/* Weather box */}
              <div className="flex items-center gap-1">
                <span>{content.weatherEmoji}</span>
                <span className="text-gray-500">今日天气：{content.weather}</span>
              </div>

              {/* Vertical divider */}
              <div className="w-px h-3 bg-gray-900/10 mx-2" />

              {/* Mini classified ad */}
              <div className="text-gray-400 truncate">
                {content.miniAd}
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Claimed state */
        <div className="text-center px-4 py-5">
          <span className="text-3xl">📰</span>
          <p className="text-sm text-gray-400 mt-2 font-semibold" style={{ fontFamily: serif }}>
            今日报纸已阅
          </p>
          <p className="text-[11px] text-gray-400 mt-0.5" style={{ fontFamily: serif }}>
            明日新刊敬请期待
          </p>
        </div>
      )}

      {/* Bottom rules */}
      <div className={`h-px mx-3 ${muted ? 'bg-gray-200' : 'bg-gray-900/30'}`} />
      <div className={`h-[2.5px] mt-[2px] ${muted ? 'bg-gray-300' : 'bg-gray-900'}`} />
    </div>
  )
}
