import { useState } from 'react'
import { Edit2, ArrowRight, ArrowLeft, AlertTriangle, Video, Image as ImageIcon, Check } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import {
  Btn, Page, PageHero, ActionBar, Modal, Input, Textarea, SegmentTag, SEGMENT_BAR, Stat, Card,
} from '../../components/ui'
import { EASE, Stagger, StaggerItem, motion } from '../../components/motion'

const TARGET_SECONDS = 30
const MAX_CAPTION_WORDS = 5

/** "00:05" / "0:05" → 5 */
const secs = (t) => {
  const [m, s] = String(t || '0:00').split(':').map(Number)
  return (m || 0) * 60 + (s || 0)
}
const clock = (n) => `${Math.floor(n / 60)}:${String(Math.round(n % 60)).padStart(2, '0')}`
const words = (t) => (String(t || '').trim().match(/\S+/g) || []).length

/** Everything the "Plan check" and action bar show, measured from the plan. */
function measure(plan, wordBudget) {
  const scenes = plan.scenes || []
  const durations = scenes.map((s) => Math.max(0, secs(s.endTime) - secs(s.startTime)))
  const total = scenes.length ? secs(scenes[scenes.length - 1].endTime) : 0
  const inOrder = scenes.every((s, i) => i === 0 || secs(s.startTime) >= secs(scenes[i - 1].endTime) - 0.01)
  const spoken = scenes.reduce((n, s) => n + words(s.voiceover), 0)
  const longCaptions = scenes.filter((s) => words(s.caption) > MAX_CAPTION_WORDS).length
  const avg = durations.length ? durations.reduce((a, b) => a + b, 0) / durations.length : 0
  return { scenes, durations, total, inOrder, spoken, longCaptions, avg, wordBudget }
}

export default function ProductionScreen() {
  const { productionPlan, setProductionPlan, selectedTopic, creatorProfile, navigate } = useApp()
  const [editScene, setEditScene] = useState(null)
  const [editForm, setEditForm] = useState({})

  if (!productionPlan) return null

  // Word budget: 30 s at the creator's measured speaking speed (fallback 160 wpm)
  const wpm = creatorProfile?.rawProfile?.audio_analysis?.mean_speech_rate_wpm || 160
  const m = measure(productionPlan, Math.round((TARGET_SECONDS / 60) * wpm))
  const timingOk = Math.abs(m.total - TARGET_SECONDS) <= 3
  const wordsOk = Math.abs(m.spoken / m.wordBudget - 1) <= 0.15

  const openEdit = (scene) => { setEditScene(scene); setEditForm({ ...scene }) }
  const saveEdit = () => {
    setProductionPlan((prev) => ({ ...prev, scenes: prev.scenes.map((s) => (s.id === editForm.id ? { ...editForm } : s)) }))
    setEditScene(null)
  }
  const setF = (k) => (e) => setEditForm((f) => ({ ...f, [k]: e.target.value }))

  return (
    <Page art="production">
      <PageHero
        step="03"
        label="Production"
        title={['Production', 'Plan']}
        topic={selectedTopic?.topic}
        lead="Your chosen script, broken into shots. Edit anything — timing and word budget update live."
      />

      <Timeline scenes={m.scenes} durations={m.durations} total={Math.max(m.total, TARGET_SECONDS)} checks={[
        { label: `${m.scenes.length} scenes ${m.inOrder ? 'in order' : 'out of order'}`, ok: m.inOrder },
        { label: `Total ${clock(m.total)} / ${clock(TARGET_SECONDS)}`, ok: timingOk },
        { label: `${m.spoken} of ~${m.wordBudget} words`, ok: wordsOk },
        { label: m.longCaptions ? `${m.longCaptions} caption${m.longCaptions > 1 ? 's' : ''} over ${MAX_CAPTION_WORDS} words` : `Captions under ${MAX_CAPTION_WORDS + 1} words`, ok: !m.longCaptions },
      ]} />

      <Card as="section" shadow={false} className="mt-9 overflow-hidden">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-vh-night px-5 py-4 sm:px-8">
          <h2 className="display text-[2.2rem]">Shot list · {m.scenes.length} scenes</h2>
          <span className="font-mono text-[14px]">{clock(m.total)} / {clock(TARGET_SECONDS)}</span>
        </header>
        <Stagger as="ol" gap={0.07} className="divide-y divide-vh-night/15">
          {m.scenes.map((scene, i) => {
            const d = m.durations[i]
            const long = m.avg > 0 && d > m.avg * 1.6
            return (
              <StaggerItem as="li" key={scene.id} className="grid gap-x-8 gap-y-4 px-5 py-6 transition-colors hover:bg-vh-cream/50 sm:px-8 md:grid-cols-[8.5rem_minmax(0,1fr)_minmax(0,16rem)_auto]">
                <div>
                  <p className="display text-[3.4rem] leading-[0.85] text-vh-accent2 tabular">{String(i + 1).padStart(2, '0')}</p>
                  <div className="mt-2"><SegmentTag segment={scene.segment} /></div>
                  <p className="mt-2 font-mono text-[12px]">{scene.startTime}–{scene.endTime} · {d} s</p>
                </div>

                <div className="min-w-0">
                  <p className="text-[17px] font-medium leading-relaxed">{scene.voiceover}</p>
                  {scene.caption && (
                    <p className="mt-3 flex flex-wrap items-center gap-2.5 text-[15px]">
                      Caption
                      <span className="rounded bg-vh-night px-2 py-0.5 text-[14px] font-bold uppercase text-vh-cream">{scene.caption}</span>
                      {words(scene.caption) > MAX_CAPTION_WORDS && <span className="font-semibold text-vh-accent2">long for a caption</span>}
                    </p>
                  )}
                  {long && (
                    <p className="mt-3 flex items-center gap-1.5 text-[14px] font-semibold text-vh-warn">
                      <AlertTriangle size={14} /> {d} s — your average scene here is {Math.round(m.avg)} s. Consider splitting.
                    </p>
                  )}
                </div>

                <dl className="space-y-3">
                  <div>
                    <dt className="flex items-center gap-1.5 font-mono text-[12px]"><Video size={12} /> Shot</dt>
                    <dd className="mt-0.5 text-[16px] font-semibold">{scene.shot || '—'}</dd>
                  </div>
                  <div>
                    <dt className="flex items-center gap-1.5 font-mono text-[12px]"><ImageIcon size={12} /> Visual</dt>
                    <dd className="mt-0.5 text-[16px] font-semibold">{scene.visual || '—'}</dd>
                  </div>
                </dl>

                <div className="md:text-right">
                  <button type="button" onClick={() => openEdit(scene)}
                    className="inline-flex h-12 items-center gap-1.5 rounded-xl border-2 border-vh-night bg-vh-cream px-4 text-[16px] font-bold transition hover:bg-vh-accent">
                    <Edit2 size={15} /> Edit
                  </button>
                </div>
              </StaggerItem>
            )
          })}
        </Stagger>
      </Card>

      <ActionBar actions={<>
        <Btn variant="secondary" icon={ArrowLeft} onClick={() => navigate('script')}>Back to scripts</Btn>
        <Btn size="lg" iconRight={ArrowRight} onClick={() => navigate('output')}>Continue to output</Btn>
      </>}>
        <Stat label="Duration" value={`${clock(m.total)} / ${clock(TARGET_SECONDS)}`} />
        <Stat label="Voiceover" value={`${m.spoken} / ~${m.wordBudget} words`} />
        <Stat label="Scenes" value={m.scenes.length} />
      </ActionBar>

      <Modal open={!!editScene} onClose={() => setEditScene(null)} title={`Edit scene · ${editForm.segment || ''}`} width="max-w-2xl">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Input label="Start" value={editForm.startTime || ''} onChange={setF('startTime')} placeholder="0:00" />
            <Input label="End" value={editForm.endTime || ''} onChange={setF('endTime')} placeholder="0:05" />
          </div>
          <Textarea label="Voiceover" value={editForm.voiceover || ''} onChange={setF('voiceover')} rows={3}
            hint={`${words(editForm.voiceover)} words`} />
          <Input label="Caption overlay" value={editForm.caption || ''} onChange={setF('caption')}
            hint={`${words(editForm.caption)} words · keep it under ${MAX_CAPTION_WORDS + 1}`} />
          <Input label="Shot" value={editForm.shot || ''} onChange={setF('shot')} placeholder="e.g. Close-up, talking to camera" />
          <Textarea label="Visual / B-roll" value={editForm.visual || ''} onChange={setF('visual')} rows={2} />
          <div className="flex justify-end gap-2 pt-1">
            <Btn variant="ghost" onClick={() => setEditScene(null)}>Cancel</Btn>
            <Btn onClick={saveEdit}>Save scene</Btn>
          </div>
        </div>
      </Modal>
    </Page>
  )
}

/** Black "Plan check" panel: measured checks as pills, then one block per scene, proportional to its length. */
function Timeline({ scenes, durations, total, checks = [] }) {
  const legend = [...new Set(scenes.map((s) => s.segment))]
  const ticks = [0, 10, 20, 30].filter((t) => t <= total)
  return (
    <Card tone="dark" className="p-6 sm:p-8">
      <div className="flex flex-wrap items-center gap-2.5">
        <span className="display mr-2 text-[2.2rem]">Plan check</span>
        {checks.map(({ label, ok }) => (
          <span key={label} className={`inline-flex items-center gap-1.5 rounded-full border-2 px-3 py-1 text-[14px] font-semibold
            ${ok ? 'border-vh-cream text-vh-cream' : 'border-vh-accent bg-vh-accent text-vh-ink'}`}>
            {ok ? <Check size={14} strokeWidth={3} /> : <AlertTriangle size={14} />}{label}
          </span>
        ))}
      </div>
      <div className="mb-4 mt-7 flex flex-wrap items-center justify-between gap-3">
        <p className="font-mono text-[13px] uppercase tracking-[0.08em]">Timeline</p>
        <ul className="flex flex-wrap gap-x-4 gap-y-1">
          {legend.map((seg) => (
            <li key={seg} className="flex items-center gap-1.5 font-mono text-[13px] capitalize">
              <span className={`h-3 w-3 rounded-sm ${SEGMENT_BAR[seg] || SEGMENT_BAR.CONCLUSION}`} />{seg.toLowerCase()}
            </li>
          ))}
        </ul>
      </div>
      <div className="flex h-5 gap-1 rounded bg-vh-frame">
        {scenes.map((s, i) => (
          <motion.div key={s.id} title={`${s.segment} · ${durations[i]} s`}
            className={`origin-left rounded-sm ${SEGMENT_BAR[s.segment] || SEGMENT_BAR.CONCLUSION}`}
            style={{ flexGrow: Math.max(durations[i], 0.5), flexBasis: 0 }}
            initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }}
            transition={{ duration: 0.5, ease: EASE, delay: 0.15 + i * 0.08 }} />
        ))}
        {total > durations.reduce((a, b) => a + b, 0) + 0.5 && (
          <div style={{ flexGrow: total - durations.reduce((a, b) => a + b, 0), flexBasis: 0 }} />
        )}
      </div>
      <div className="relative mt-3 h-4 font-mono text-[13px]">
        {ticks.map((t) => (
          <span key={t} className="absolute -translate-x-1/2 first:translate-x-0 last:-translate-x-full" style={{ left: `${(t / total) * 100}%` }}>
            {clock(t)}
          </span>
        ))}
      </div>
    </Card>
  )
}
