import { useState } from 'react'
import { ArrowLeft, ArrowRight, Check, Plus, X, Lightbulb } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { Btn, Badge, Page, PageHero, ActionBar, Input, EmptyState, Card } from '../../components/ui'
import { Stagger, StaggerItem } from '../../components/motion'

export default function TopicSelectScreen() {
  const { selectedTopic, setSelectedTopic, trendingTopics, navigate } = useApp()
  // Real research topics; or just the own idea when coming from that path
  const topics = trendingTopics.length > 0 ? trendingTopics : (selectedTopic ? [selectedTopic] : [])
  const [picked, setPicked] = useState(selectedTopic)
  const [useOwn, setUseOwn] = useState(false)
  const [ownText, setOwnText] = useState('')

  const toggle = (t) => setPicked((prev) => (prev?.id === t.id ? null : t))
  const pickOwn = () => {
    if (!ownText.trim()) return
    setPicked({ id: 'own_' + Date.now(), topic: ownText.trim(), trendScore: null, creatorFit: null, isOwn: true })
    setUseOwn(false)
  }
  const proceed = () => {
    if (!picked) return
    setSelectedTopic(picked)
    navigate('script')
  }
  const list = picked?.isOwn && !topics.some((t) => t.id === picked.id) ? [picked, ...topics] : topics

  return (
    <Page art="topics">
      <button type="button" onClick={() => navigate('ideation')}
        className="mb-6 inline-flex items-center gap-1.5 text-[15px] font-semibold underline-offset-4 hover:underline">
        <ArrowLeft size={16} /> Back to ideation
      </button>
      <PageHero
        step="01"
        label="Ideation"
        title={['Pick your', 'Topic']}
        lead="Pick the topic for this video. Click a selected topic again to clear it."
      />

      {list.length === 0 ? (
        <Card shadow={false}><EmptyState icon={Lightbulb} title="No topics loaded">Go back and find trending ideas, or write your own below.</EmptyState></Card>
      ) : (
        <Stagger role="radiogroup" aria-label="Topics" className="space-y-4">
          {list.map((t, i) => {
            const on = picked?.id === t.id
            return (
              <StaggerItem key={t.id}>
                <button type="button" role="radio" aria-checked={on} onClick={() => toggle(t)}
                  className={`flex w-full items-center gap-5 rounded-2xl border-2 border-vh-night bg-white p-5 text-left transition-[transform,box-shadow] duration-200 sm:p-6
                    ${on ? 'shadow-accent' : 'hover:-translate-y-0.5 hover:shadow-hard-sm'}`}>
                  <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-vh-night
                    ${on ? 'bg-vh-accent' : 'bg-white'}`}>
                    {on && <Check size={16} strokeWidth={3.5} />}
                  </span>
                  <span className="display hidden w-11 shrink-0 text-[2.6rem] leading-[0.85] text-vh-accent2 sm:block">{String(i + 1).padStart(2, '0')}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[18px] font-bold">{t.topic}</span>
                      {t.isOwn && <Badge color="pop">Your idea</Badge>}
                      {on && <Badge color="ok">Selected</Badge>}
                    </div>
                    {t.whyThis && <p className="mt-1 text-[15px] leading-relaxed">{t.whyThis}</p>}
                  </div>
                  {(t.trendScore != null || t.creatorFit != null) && (
                    <div className="hidden shrink-0 gap-6 text-right sm:flex">
                      <Metric label="Trend" value={t.trendScore} />
                      <Metric label="Fit" value={t.creatorFit} />
                    </div>
                  )}
                </button>
              </StaggerItem>
            )
          })}
        </Stagger>
      )}

      <div className="mt-6">
        {!useOwn ? (
          <Btn variant="secondary" icon={Plus} onClick={() => { setUseOwn(true) }}>Use my own idea instead</Btn>
        ) : (
          <Card className="max-w-2xl p-5 sm:p-6">
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[14rem] flex-1">
                <Input label="Your idea" value={ownText} autoFocus onChange={(e) => setOwnText(e.target.value)}
                  placeholder="e.g. Why most developers learn the wrong things"
                  onKeyDown={(e) => e.key === 'Enter' && pickOwn()} />
              </div>
              <Btn onClick={pickOwn} disabled={!ownText.trim()} className="h-12">Use</Btn>
              <Btn variant="ghost" icon={X} onClick={() => setUseOwn(false)} className="h-12">Cancel</Btn>
            </div>
          </Card>
        )}
      </div>

      <ActionBar actions={
        <Btn size="lg" disabled={!picked} onClick={proceed} iconRight={ArrowRight}>Generate scripts</Btn>
      }>
        <div className="min-w-0">
          <p className="font-mono text-[12px]">Selected topic</p>
          <p className="max-w-[46ch] truncate text-lg font-bold">{picked?.topic || 'Nothing selected yet'}</p>
        </div>
      </ActionBar>
    </Page>
  )
}

function Metric({ label, value }) {
  return (
    <div>
      <p className="display text-[2.4rem] leading-[0.85] tabular">{value ?? '—'}</p>
      <p className="mt-1 font-mono text-[12px]">{label}</p>
    </div>
  )
}
