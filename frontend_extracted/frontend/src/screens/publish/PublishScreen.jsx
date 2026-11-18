import { useState, useEffect } from 'react'
import { ArrowRight, CircleCheck, Film, ChevronDown } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { getInstagramAccount, publishNow, schedulePost, generateCaption } from '../../services/api'
import {
  Btn, Card, Badge, Page, PageHero, Alert, Input, ActionBar, Segmented, Stat, Spinner,
} from '../../components/ui'

const STATUS_TONE = { Draft: 'muted', Processing: 'warn', Scheduled: 'info', Published: 'ok', Failed: 'bad' }
const WHEN = [{ value: 'now', label: 'Publish now' }, { value: 'schedule', label: 'Schedule' }]
const MAX_CAPTION = 2200   // Instagram's caption limit

export default function PublishScreen() {
  const { selectedTopic, selectedVariant, videoResult, publishStatus, setPublishStatus } = useApp()
  const [account, setAccount] = useState(null)
  const [caption, setCaption] = useState('')
  const [schedDate, setSchedDate] = useState('')
  const [schedTime, setSchedTime] = useState('18:00')
  const [when, setWhen] = useState('now')
  const [status, setStatus] = useState(publishStatus || null) // null | publishing | scheduling | published | scheduled
  const [showHistory, setShowHistory] = useState(false)

  useEffect(() => {
    getInstagramAccount().then(({ account: a }) => setAccount(a))
    generateCaption({ topic: selectedTopic?.topic }).then(({ caption: c }) => setCaption(c))
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    setSchedDate(tomorrow.toISOString().split('T')[0])
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    if (when === 'now') {
      setStatus('publishing')
      await publishNow({ caption })
      setStatus('published')
      setPublishStatus('published')
    } else {
      if (!schedDate || !schedTime) return
      setStatus('scheduling')
      await schedulePost({ caption, date: schedDate, time: schedTime })
      setStatus('scheduled')
      setPublishStatus('scheduled')
    }
  }

  const title = selectedVariant?.topic || selectedTopic?.topic || 'Your video'
  const busy = status === 'publishing' || status === 'scheduling'
  const finished = status === 'published' || status === 'scheduled'
  const history = [
    { id: 1, title, status: status === 'published' ? 'Published' : status === 'scheduled' ? 'Scheduled' : 'Draft', date: status === 'scheduled' ? `${schedDate} ${schedTime}` : 'Now' },
    { id: 2, title: 'Why most developers are learning the wrong things', status: 'Published', date: 'Aug 18' },
    { id: 3, title: 'The quiet death of SaaS', status: 'Scheduled', date: 'Aug 27' },
  ]

  return (
    <Page art="publish">
      <PageHero
        step="05"
        label="Publish"
        title={['Publish to', 'Instagram']}
        topic={selectedTopic?.topic}
        lead="Write the caption, then post now or pick a time."
      />

      <Alert type="info" chip="Preview" className="mb-9">Instagram publishing is not connected yet, so nothing is actually posted.</Alert>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,17rem)_minmax(0,1fr)]">
        {/* Video + account */}
        <div className="space-y-5">
          <div className="relative mx-auto flex aspect-[9/16] w-full max-w-[15rem] items-center justify-center overflow-hidden rounded-2xl bg-vh-night shadow-accent sm:max-w-[17rem] lg:max-w-none">
            {videoResult?.videoUrl
              ? <video src={videoResult.videoUrl} controls playsInline className="h-full w-full object-contain" />
              : <div className="px-6 text-center"><Film size={34} className="mx-auto mb-3 text-vh-accent" /><p className="font-mono text-[14px] text-vh-cream">Exported for editing</p></div>}
          </div>
          {account && (
            <Card shadow={false} className="flex items-center gap-3 p-4">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 border-vh-night bg-vh-accent text-sm font-bold">{account.avatar}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[16px] font-bold">{account.handle}</p>
                <p className="font-mono text-[12px]">{account.followers} followers</p>
              </div>
              <Badge color="ok">Connected</Badge>
            </Card>
          )}
        </div>

        {/* Caption + timing */}
        <div className="min-w-0 space-y-6">
          <Card className="p-6 sm:p-8">
            <label htmlFor="caption" className="display block text-[2.4rem]">Caption</label>
            <textarea id="caption" value={caption} onChange={(e) => setCaption(e.target.value.slice(0, MAX_CAPTION))} rows={8}
              placeholder="Write a caption…" disabled={busy || finished}
              className="mt-4 w-full resize-y rounded-xl border-2 border-vh-night bg-vh-cream px-5 py-4 text-[17px] leading-relaxed placeholder:text-vh-night/45 focus:outline-none focus:ring-4 focus:ring-vh-accent/40 disabled:opacity-60" />
            <p className="mt-3 font-mono text-[14px] tabular">{caption.length} / {MAX_CAPTION}</p>
          </Card>

          {!finished && (
            <Card shadow={false} className="p-6 sm:px-8">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <p className="display text-[2.4rem]">When</p>
                <Segmented label="When to post" options={WHEN} value={when} onChange={setWhen} />
              </div>
              {when === 'schedule' && (
                <div className="mt-5 grid max-w-sm grid-cols-2 gap-3">
                  <Input label="Date" type="date" value={schedDate} onChange={(e) => setSchedDate(e.target.value)} />
                  <Input label="Time" type="time" value={schedTime} onChange={(e) => setSchedTime(e.target.value)} />
                </div>
              )}
            </Card>
          )}

          {busy && (
            <Card shadow={false} className="flex items-center gap-3 p-6">
              <Spinner size={20} />
              <p className="text-[16px] font-semibold">{status === 'publishing' ? 'Sending to Instagram…' : 'Scheduling your post…'}</p>
            </Card>
          )}

          {finished && (
            <Card tone="dark" className="flex items-start gap-4 p-6 sm:p-8">
              <CircleCheck size={34} className="shrink-0 text-vh-accent" />
              <div>
                <p className="display text-[2.4rem] text-vh-accent">{status === 'published' ? 'Published' : 'Scheduled'}</p>
                <p className="mt-1 text-[16px]">
                  {status === 'published' ? `Live on ${account?.handle || 'your account'}.` : `Posts on ${schedDate} at ${schedTime}.`}
                </p>
              </div>
            </Card>
          )}

          <section>
            <button type="button" onClick={() => setShowHistory((h) => !h)} aria-expanded={showHistory}
              className="inline-flex items-center gap-1.5 text-[17px] font-bold underline underline-offset-4">
              <ChevronDown size={16} strokeWidth={3} className={`transition-transform ${showHistory ? 'rotate-180' : ''}`} /> Post history
            </button>
            {showHistory && (
              <ul className="mt-4 space-y-3">
                {history.map((item) => (
                  <li key={item.id} className="flex items-center gap-3 rounded-xl border-2 border-vh-night bg-white px-4 py-3">
                    <span className="flex h-10 w-9 shrink-0 items-center justify-center rounded bg-vh-night"><Film size={14} className="text-vh-accent" /></span>
                    <span className="flex-1 truncate text-[15px] font-semibold">{item.title}</span>
                    <span className="font-mono text-[12px]">{item.date}</span>
                    <Badge color={STATUS_TONE[item.status] || 'muted'}>{item.status}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>

      <ActionBar actions={
        <Btn size="lg" iconRight={ArrowRight} loading={busy} disabled={finished} onClick={submit}>
          {when === 'now' ? 'Publish now' : 'Schedule post'}
        </Btn>
      }>
        <Stat label="Account" value={account?.handle || '—'} />
        <Stat label="Caption" value={`${caption.length} characters`} />
        <Stat label="When" value={when === 'now' ? 'Now' : `${schedDate} · ${schedTime}`} />
      </ActionBar>
    </Page>
  )
}
