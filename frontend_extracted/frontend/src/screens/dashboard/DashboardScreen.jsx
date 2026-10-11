import { useEffect, useState } from 'react'
import { Plus, TrendingUp, FileText, Clock, CheckCircle, Film, BarChart2, Users, Zap, Camera, User, Mic } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { getContentHistory } from '../../services/api'
import { Btn, Badge, Card, Page } from '../../components/ui'

const STATUS_COLOR = {
  Published: 'green',
  Scheduled: 'blurple',
  Draft:     'muted',
  Processing:'yellow',
  Failed:    'red',
}

export default function DashboardScreen() {
  const { creatorProfile, navigate } = useApp()
  const [history, setHistory] = useState([])

  useEffect(() => {
    getContentHistory().then(({ history: h }) => setHistory(h))
  }, [])

  if (!creatorProfile) return null

  const videoProfiles = creatorProfile.rawProfile?.per_video_profiles ?? []

  const stats = [
    { label: 'Published', value: creatorProfile.published, icon: CheckCircle, color: 'text-discord-green' },
    { label: 'Scheduled', value: creatorProfile.scheduled, icon: Clock, color: 'text-discord-blurple' },
    { label: 'Drafts',    value: creatorProfile.drafts,    icon: FileText, color: 'text-discord-muted' },
    { label: 'Videos Analysed', value: creatorProfile.analyzedVideos, icon: Film, color: 'text-purple-400' },
  ]

  return (
    <Page>
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between mb-8 flex-wrap gap-4">
          <div>
            <h1 className="text-discord-white font-bold text-2xl">
              Welcome back, {creatorProfile.name?.split(' ')[0]} 👋
            </h1>
            <p className="text-discord-muted text-sm mt-1">
              {creatorProfile.handle} · {creatorProfile.niche}
            </p>
          </div>
          <Btn icon={Plus} size="lg" onClick={() => navigate('ideation')}>
            Create New Video
          </Btn>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {stats.map(({ label, value, icon: Icon, color }) => (
            <Card key={label} className="p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide">{label}</p>
                <Icon size={16} className={color} />
              </div>
              <p className="text-discord-white font-bold text-2xl">{value}</p>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Creator profile card */}
          <Card className="p-5 md:col-span-1">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-discord-blurple flex items-center justify-center text-white font-bold">
                {creatorProfile.name?.[0]?.toUpperCase()}
              </div>
              <div>
                <p className="text-discord-white font-semibold text-sm">{creatorProfile.name}</p>
                <p className="text-discord-muted text-xs">{creatorProfile.handle}</p>
              </div>
            </div>

            <div className="space-y-3">
              <ProfileRow label="Niche" value={creatorProfile.niche} />
              <ProfileRow label="Dominant Hook" value={<Badge color="purple">{creatorProfile.dominantHookType}</Badge>} />
              <ProfileRow label="Structure" value={<span className="text-discord-text text-xs leading-tight">{creatorProfile.dominantStructure}</span>} />
            </div>

            <div className="mt-4 pt-4 border-t border-discord-faint/20">
              <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-2">Style Summary</p>
              <p className="text-discord-muted text-xs leading-relaxed line-clamp-4">{creatorProfile.styleSummary}</p>
            </div>



          </Card>

          {/* Content history */}
          <Card className="p-5 md:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-discord-white font-semibold text-sm">Recent Content</h3>
              <Btn variant="ghost" size="sm" onClick={() => navigate('ideation')}>+ New</Btn>
            </div>

            {history.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-center">
                <Film size={32} className="text-discord-faint mb-3" />
                <p className="text-discord-muted text-sm">No content yet</p>
                <p className="text-discord-faint text-xs mt-1">Create your first video to get started</p>
              </div>
            ) : (
              <div className="space-y-2">
                {history.map((item) => (
                  <div key={item.id} className="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-discord-hover transition-colors">
                    <div className="w-8 h-8 rounded bg-discord-input flex items-center justify-center flex-shrink-0">
                      <Film size={14} className="text-discord-muted" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-discord-white text-sm font-medium truncate">{item.title}</p>
                      <p className="text-discord-muted text-xs">{item.date} · {item.niche}</p>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      {item.views !== '—' && (
                        <span className="text-discord-muted text-xs flex items-center gap-1">
                          <BarChart2 size={11} /> {item.views}
                        </span>
                      )}
                      <Badge color={STATUS_COLOR[item.status] || 'muted'}>{item.status}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-4 pt-4 border-t border-discord-faint/20">
              <Btn variant="secondary" size="sm" className="w-full" onClick={() => navigate('ideation')}>
                <Plus size={14} /> Start New Video
              </Btn>
            </div>
          </Card>
        </div>

        {/* Per-video profiles (Module 2 multimodal analysis) */}
        {videoProfiles.length > 0 && (
          <div className="mt-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-discord-white font-semibold text-sm">Per-Video Analysis</h3>
              <p className="text-discord-muted text-xs">{videoProfiles.length} videos · multimodal</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {videoProfiles.map((video, i) => (
                <VideoProfileCard key={video.video_id || i} video={video} index={i} />
              ))}
            </div>
          </div>
        )}
      </div>
    </Page>
  )
}

function VideoProfileCard({ video, index }) {
  const talkingHead = typeof video.talking_head_pct === 'number'
    ? Math.round(video.talking_head_pct * 100)
    : null
  const wpm = typeof video.speech_rate_wpm === 'number' ? Math.round(video.speech_rate_wpm) : null

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded bg-discord-input flex items-center justify-center flex-shrink-0">
            <Film size={13} className="text-discord-muted" />
          </div>
          <div className="min-w-0">
            <p className="text-discord-white text-sm font-medium">Video {index + 1}</p>
            {video.video_id && (
              <p className="text-discord-faint text-[10px] font-mono truncate" title={video.video_id}>{video.video_id}</p>
            )}
          </div>
        </div>
        {video.hook_type && <Badge color="purple">{video.hook_type}</Badge>}
      </div>

      <div className="space-y-2.5">
        <VideoMetric icon={Zap} label="Pacing" value={video.visual_pacing} />
        <VideoMetric icon={Camera} label="Shots" value={video.shot_count} />
        <VideoMetric icon={Mic} label="Speech" value={wpm !== null ? `${wpm} wpm` : null} />
        <div>
          <VideoMetric icon={User} label="Talking head" value={talkingHead !== null ? `${talkingHead}%` : null} />
          {talkingHead !== null && (
            <div className="mt-1.5 h-1.5 rounded-full bg-discord-input overflow-hidden">
              <div className="h-full rounded-full bg-discord-blurple" style={{ width: `${talkingHead}%` }} />
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}

function VideoMetric({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="flex items-center gap-1.5 text-discord-faint text-xs font-semibold uppercase tracking-wide">
        <Icon size={11} /> {label}
      </span>
      <span className="text-discord-text text-xs text-right">{value ?? '—'}</span>
    </div>
  )
}

function ProfileRow({ label, value }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-discord-faint text-xs font-semibold uppercase tracking-wide w-20 flex-shrink-0 pt-0.5">{label}</span>
      <span className="text-discord-text text-xs">{value}</span>
    </div>
  )
}
