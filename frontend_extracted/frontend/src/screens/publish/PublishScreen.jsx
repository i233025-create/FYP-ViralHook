import { useState, useEffect } from 'react'
import { Instagram, CheckCircle, Clock, Send, Calendar, Film } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { getInstagramAccount, publishNow, schedulePost, generateCaption } from '../../services/api'
import { Btn, Card, Badge, SectionHeader, Page, Alert, Textarea, Input } from '../../components/ui'

const STATUS_FLOW = ['Draft', 'Processing', 'Scheduled', 'Published']
const STATUS_COLOR = {
  Draft:     'muted',
  Processing:'yellow',
  Scheduled: 'blurple',
  Published: 'green',
  Failed:    'red',
}

export default function PublishScreen() {
  const { selectedTopic, selectedVariant, publishStatus, setPublishStatus } = useApp()
  const [account, setAccount] = useState(null)
  const [caption, setCaption] = useState('')
  const [schedDate, setSchedDate] = useState('')
  const [schedTime, setSchedTime] = useState('18:00')
  const [mode, setMode] = useState(null) // null | 'now' | 'schedule'
  const [status, setStatus] = useState(publishStatus || null)  // null | 'publishing' | 'scheduling' | 'published' | 'scheduled'
  const [showHistory, setShowHistory] = useState(false)

  useEffect(() => {
    getInstagramAccount().then(({ account: a }) => setAccount(a))
    generateCaption({ topic: selectedTopic?.topic }).then(({ caption: c }) => setCaption(c))
    // Default schedule date = tomorrow
    const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1)
    setSchedDate(tomorrow.toISOString().split('T')[0])
  }, [])

  const handlePublishNow = async () => {
    setStatus('publishing')
    await publishNow({ caption })
    setStatus('published')
    setPublishStatus('published')
  }

  const handleSchedule = async () => {
    if (!schedDate || !schedTime) return
    setStatus('scheduling')
    await schedulePost({ caption, date: schedDate, time: schedTime })
    setStatus('scheduled')
    setPublishStatus('scheduled')
  }

  const CONTENT_HISTORY_DEMO = [
    { id: 1, title: selectedVariant?.topic || 'AI Agents & Dev', status: status === 'published' ? 'Published' : status === 'scheduled' ? 'Scheduled' : 'Draft', date: status === 'scheduled' ? `${schedDate} ${schedTime}` : 'Now' },
    { id: 2, title: 'Why Most Developers Are Learning Wrong', status: 'Published', date: 'Aug 18' },
    { id: 3, title: 'The Quiet Death of SaaS', status: 'Scheduled', date: 'Aug 27' },
  ]

  return (
    <Page>
      <div className="max-w-xl mx-auto">
        <SectionHeader icon={Instagram} title="Publish" subtitle="Share your content to Instagram or schedule for later." />

        {/* Account status */}
        {account && (
          <Card className="p-4 mb-5 flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-discord-blurple flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
              {account.avatar}
            </div>
            <div className="flex-1">
              <p className="text-discord-white font-semibold text-sm">{account.handle}</p>
              <p className="text-discord-muted text-xs">{account.followers} followers</p>
            </div>
            <Badge color="green">● Connected</Badge>
          </Card>
        )}

        {/* Video preview placeholder */}
        <Card className="p-4 mb-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-16 h-16 rounded-xl bg-discord-blurple/20 flex items-center justify-center flex-shrink-0">
              <Film size={24} className="text-discord-blurple" />
            </div>
            <div>
              <p className="text-discord-white text-sm font-semibold">{selectedVariant?.topic || selectedTopic?.topic || 'Your Video'}</p>
              <p className="text-discord-muted text-xs">{selectedVariant?.hookType || 'Script ready'} · 27s</p>
              <Badge color="green" size="sm">Ready to publish</Badge>
            </div>
          </div>
        </Card>

        {/* Caption */}
        <div className="mb-5">
          <Textarea
            label="Caption"
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            rows={5}
            placeholder="Write a caption..."
          />
        </div>

        {/* Publish / Schedule */}
        {!status && (
          <div className="space-y-3">
            {!mode && (
              <div className="grid grid-cols-2 gap-3">
                <Btn size="lg" icon={Send} onClick={() => setMode('now')}>Publish Now</Btn>
                <Btn size="lg" variant="secondary" icon={Calendar} onClick={() => setMode('schedule')}>Schedule Post</Btn>
              </div>
            )}

            {mode === 'now' && (
              <Card className="p-4 animate-fadeIn">
                <p className="text-discord-white text-sm font-semibold mb-3">Publish immediately</p>
                <p className="text-discord-muted text-xs mb-4">Your video will be posted to {account?.handle} right away.</p>
                <div className="flex gap-3">
                  <Btn className="flex-1" icon={Send} onClick={handlePublishNow}>Confirm & Publish</Btn>
                  <Btn variant="secondary" onClick={() => setMode(null)}>Cancel</Btn>
                </div>
              </Card>
            )}

            {mode === 'schedule' && (
              <Card className="p-4 animate-fadeIn">
                <p className="text-discord-white text-sm font-semibold mb-3">Schedule post</p>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <Input label="Date" type="date" value={schedDate} onChange={(e) => setSchedDate(e.target.value)} />
                  <Input label="Time" type="time" value={schedTime} onChange={(e) => setSchedTime(e.target.value)} />
                </div>
                <div className="flex gap-3">
                  <Btn className="flex-1" icon={Calendar} onClick={handleSchedule}>Confirm Schedule</Btn>
                  <Btn variant="secondary" onClick={() => setMode(null)}>Cancel</Btn>
                </div>
              </Card>
            )}
          </div>
        )}

        {/* Publishing states */}
        {status === 'publishing' && (
          <Card className="p-6 text-center animate-fadeIn">
            <div className="w-12 h-12 rounded-full bg-discord-blurple/20 flex items-center justify-center mx-auto mb-3">
              <Send size={22} className="text-discord-blurple animate-pulse" />
            </div>
            <p className="text-discord-white font-semibold">Publishing…</p>
            <p className="text-discord-muted text-sm mt-1">Sending to Instagram</p>
          </Card>
        )}

        {status === 'scheduling' && (
          <Card className="p-6 text-center animate-fadeIn">
            <div className="w-12 h-12 rounded-full bg-discord-blurple/20 flex items-center justify-center mx-auto mb-3">
              <Clock size={22} className="text-discord-blurple animate-pulse" />
            </div>
            <p className="text-discord-white font-semibold">Scheduling…</p>
            <p className="text-discord-muted text-sm mt-1">Setting up your post</p>
          </Card>
        )}

        {status === 'published' && (
          <Card className="p-6 text-center border-discord-green/30 animate-fadeIn">
            <div className="w-12 h-12 rounded-full bg-discord-green/20 flex items-center justify-center mx-auto mb-3">
              <CheckCircle size={22} className="text-discord-green" />
            </div>
            <p className="text-discord-white font-bold text-lg">Published!</p>
            <p className="text-discord-muted text-sm mt-1">Your video is now live on {account?.handle}</p>
            <Badge color="green" size="lg" className="mt-3 inline-block">Published</Badge>
          </Card>
        )}

        {status === 'scheduled' && (
          <Card className="p-6 text-center border-discord-blurple/30 animate-fadeIn">
            <div className="w-12 h-12 rounded-full bg-discord-blurple/20 flex items-center justify-center mx-auto mb-3">
              <Calendar size={22} className="text-discord-blurple" />
            </div>
            <p className="text-discord-white font-bold text-lg">Scheduled Successfully</p>
            <p className="text-discord-muted text-sm mt-1">Will post on {schedDate} at {schedTime}</p>
            <Badge color="blurple" size="lg" className="mt-3 inline-block">Scheduled</Badge>
          </Card>
        )}

        {/* Content status history */}
        <div className="mt-8">
          <button
            onClick={() => setShowHistory(h => !h)}
            className="text-discord-muted text-sm hover:text-discord-white transition-colors mb-3"
          >
            {showHistory ? '▼' : '▶'} Content Status History
          </button>
          {showHistory && (
            <div className="space-y-2 animate-fadeIn">
              {CONTENT_HISTORY_DEMO.map((item) => (
                <div key={item.id} className="flex items-center gap-3 px-3 py-2.5 bg-discord-sidebar rounded-lg border border-discord-faint/20">
                  <Film size={14} className="text-discord-muted flex-shrink-0" />
                  <span className="flex-1 text-discord-white text-xs truncate">{item.title}</span>
                  <span className="text-discord-faint text-xs">{item.date}</span>
                  <Badge color={STATUS_COLOR[item.status] || 'muted'} size="sm">{item.status}</Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Page>
  )
}
