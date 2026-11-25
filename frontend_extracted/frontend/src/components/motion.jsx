// ─────────────────────────────────────────────────────────────────────────────
// Motion kit (framer-motion). One easing and a few durations for the whole app,
// so every movement feels like the same product. Everything respects the
// user's "reduce motion" setting (MotionConfig reducedMotion="user" in App.jsx).
//
//   PageTransition   fade + small rise when the screen changes
//   Reveal           fade + rise when a block scrolls into view (once)
//   Stagger / StaggerItem   children appear one after another
//   CountUp          numbers count up from 0 when they come into view
// ─────────────────────────────────────────────────────────────────────────────
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, animate, motion, useInView, useReducedMotion } from 'framer-motion'

export const EASE = [0.22, 1, 0.36, 1]          // quick start, soft landing
export const DURATION = { fast: 0.18, base: 0.32, slow: 0.6 }

const tag = (as) => (typeof as === 'string' ? motion[as] : motion.div)

/** Wraps the current screen; `screenKey` changes → old screen out, new screen in. */
export function PageTransition({ screenKey, children }) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={screenKey}
        className="flex min-h-full flex-1 flex-col"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0, transition: { duration: DURATION.base, ease: EASE } }}
        exit={{ opacity: 0, y: -6, transition: { duration: DURATION.fast, ease: 'easeIn' } }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}

/** Fade + rise the first time the block enters the viewport. */
export function Reveal({ as, delay = 0, y = 16, className, children, ...rest }) {
  const M = tag(as)
  return (
    <M
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: DURATION.slow, ease: EASE, delay }}
      {...rest}
    >
      {children}
    </M>
  )
}

const container = (gap, delay) => ({
  hidden: {},
  show: { transition: { staggerChildren: gap, delayChildren: delay } },
})
const item = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: DURATION.slow, ease: EASE } },
}

/** Parent of StaggerItems: they appear one after another when the list comes into view. */
export function Stagger({ as, gap = 0.06, delay = 0, className, children, ...rest }) {
  const M = tag(as)
  return (
    <M className={className} variants={container(gap, delay)} initial="hidden" whileInView="show"
      viewport={{ once: true, amount: 0.05 }} {...rest}>
      {children}
    </M>
  )
}

export function StaggerItem({ as, className, children, ...rest }) {
  const M = tag(as)
  return <M className={className} variants={item} {...rest}>{children}</M>
}

/**
 * Counts from 0 to `value` once visible. Non-numbers (—, "0:27") are shown as-is.
 * `decimals` for values like 0.912.
 */
export function CountUp({ value, duration = 0.9, decimals = 0, className }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, amount: 0.6 })
  const reduce = useReducedMotion()
  const numeric = typeof value === 'number' && Number.isFinite(value)
  const [shown, setShown] = useState(numeric && !reduce ? 0 : value)

  useEffect(() => {
    if (!numeric) { setShown(value); return undefined }
    if (reduce) { setShown(value); return undefined }
    if (!inView) return undefined
    const controls = animate(0, value, { duration, ease: EASE, onUpdate: (v) => setShown(v) })
    return () => controls.stop()
  }, [inView, value, numeric, reduce, duration])

  const text = numeric ? Number(shown).toFixed(decimals) : value
  return <span ref={ref} className={className}>{text}</span>
}

export { AnimatePresence, motion }
