import { motion } from 'framer-motion'
import useDailyTaskStore from '@/store/useDailyTaskStore'

interface InspirationDailyProps {
  className?: string
  /** Called when the tear zone is activated (swipe complete). Wired in #375. */
  onTear?: () => void
}

const DAILY_PROMPTS = [
  '今天画一只会飞的鱼吧！🐟✨',
  '如果云朵是棉花糖，你会怎么画？🍬☁️',
  '画一个住在树上的小精灵 🧚‍♂️🌳',
  '想象一下海底的城堡长什么样？🏰🌊',
  '给你的宠物设计一件超级英雄披风！🦸‍♀️',
  '画一列开往星星的火车 🚂⭐',
  '如果恐龙还活着，它会做什么工作？🦕💼',
  '设计一个能在水上跑的鞋子 👟💧',
  '画一个用彩虹做的滑梯 🌈',
  '如果你有一根魔法棒，你会变出什么？🪄',
  '画一个会唱歌的花朵 🌸🎵',
  '想象月亮上有一个游乐场 🌙🎠',
  '给一只猫咪设计一顶帽子 🐱🎩',
  '画一个用糖果盖的房子 🍭🏠',
  '如果你是一条龙，你的家在哪里？🐉',
  '设计一个能飞的书包 🎒✈️',
  '画一片会变颜色的森林 🌲🎨',
  '想象一个用音符做的桥 🎶🌉',
  '给太阳画一副墨镜 ☀️😎',
  '画一个住在蘑菇里的小矮人 🍄',
  '如果大海是果汁做的，你想跳进去吗？🧃🏊',
  '设计一艘用冰淇淋做的船 🍦🚢',
  '画一只穿溜冰鞋的企鹅 🐧⛸️',
  '如果你能养一只神奇动物，你想养什么？🦄',
  '画一个在天上飘的花园 🌺☁️',
  '想象你的房间变成了太空站 🚀🛸',
  '给一只青蛙设计一个王冠 🐸👑',
  '画一棵长满棒棒糖的树 🍭🌴',
  '如果雨滴是彩色的，世界会变成什么样？🌧️🎨',
  '设计一个能跟你说话的机器人朋友 🤖💬',
  '画一条用星星铺成的路 ⭐🛤️',
]

function getDailyPrompt(): string {
  const now = new Date()
  const start = new Date(now.getFullYear(), 0, 0)
  const dayOfYear = Math.floor((now.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
  return DAILY_PROMPTS[dayOfYear % DAILY_PROMPTS.length]
}

function formatDate(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const weekdays = ['日', '一', '二', '三', '四', '五', '六']
  const weekday = weekdays[now.getDay()]
  return `${year}年${month}月${day}日 星期${weekday}`
}

export default function InspirationDaily({ className = '', onTear }: InspirationDailyProps) {
  const canClaim = useDailyTaskStore((s) => s.canClaimToday())
  const prompt = getDailyPrompt()
  const dateStr = formatDate()

  return (
    <div
      className={`relative overflow-hidden rounded-card shadow-card font-rounded
        ${canClaim ? 'bg-warm-50' : 'bg-warm-200 opacity-75'} ${className}`}
      style={{
        backgroundImage: canClaim
          ? 'repeating-linear-gradient(0deg, transparent, transparent 28px, rgba(200,180,160,0.1) 28px, rgba(200,180,160,0.1) 29px)'
          : 'none',
      }}
    >
      {/* Tear zone — top ~30% */}
      <div
        className="relative cursor-grab active:cursor-grabbing select-none"
        onClick={canClaim ? onTear : undefined}
      >
        {/* Masthead */}
        <div className="px-4 pt-4 pb-3 text-center">
          <h3
            className={`text-xl sm:text-2xl font-bold tracking-wide ${
              canClaim ? 'text-accent-dark' : 'text-gray-400'
            }`}
          >
            📰 灵感日报
          </h3>
          <p className={`text-xs mt-0.5 ${canClaim ? 'text-gray-500' : 'text-gray-400'}`}>
            {dateStr}
          </p>
        </div>

        {/* Tear line hint */}
        <div className="relative h-3 flex items-center">
          <div
            className={`w-full border-t-2 border-dashed ${
              canClaim ? 'border-accent/40' : 'border-gray-300'
            }`}
          />
          {canClaim && (
            <motion.div
              className="absolute right-3 text-xs text-accent-dark/60"
              animate={{ x: [0, 6, 0] }}
              transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut' }}
            >
              👉 滑动撕开
            </motion.div>
          )}
        </div>
      </div>

      {/* Content area */}
      <div className="px-4 pb-4 pt-2">
        {canClaim ? (
          <>
            <p className="text-sm sm:text-base text-gray-700 leading-relaxed">
              {prompt}
            </p>
            <motion.p
              className="mt-2 text-xs text-accent-dark/70 font-semibold"
              animate={{ scale: [1, 1.03, 1] }}
              transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
            >
              ⬆️ 撕开报纸领取今日星星 🌟
            </motion.p>
          </>
        ) : (
          <div className="text-center py-2">
            <span className="text-2xl">✅</span>
            <p className="text-sm text-gray-500 mt-1">今日已领取，明天再来哦！</p>
          </div>
        )}
      </div>
    </div>
  )
}
