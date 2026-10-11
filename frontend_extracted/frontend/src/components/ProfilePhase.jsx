import { useState } from 'react'
import { User, Film, ChevronRight, ChevronDown, ChevronUp, Zap, MessageSquare, Clock, Target, Repeat } from 'lucide-react'
import { PHASES } from '../phases'
import ChannelHeader from './ChannelHeader'

function Badge({ children, color = 'blurple' }) {
  const colors = {
    blurple: 'bg-discord-blurple/20 text-discord-blurple border-discord-blurple/30',
    green:   'bg-discord-green/20 text-discord-green border-discord-green/30',
    yellow:  'bg-discord-yellow/20 text-discord-yellow border-discord-yellow/30',
    purple:  'bg-purple-500/20 text-purple-400 border-purple-500/30',
    cyan:    'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${colors[color]}`}>
      {children}
    </span>
  )
}

function VideoProfileCard({ vp, index }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="bg-discord-sidebar border border-discord-faint/20 rounded-lg overflow-hidden transition-colors hover:border-discord-faint/40">
      {/* Header row */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-discord-blurple/20 text-discord-blurple font-bold text-sm flex-shrink-0">
          {index + 1}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-discord-white font-medium text-sm truncate">{vp.videoName}</p>
          <p className="text-discord-muted text-xs">{vp.topic}</p>
        </div>
        <Badge color="purple">{vp.hookType}</Badge>
        {open ? <ChevronUp size={16} className="text-discord-muted flex-shrink-0" /> : <ChevronDown size={16} className="text-discord-muted flex-shrink-0" />}
      </button>

      {/* Expanded details */}
      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-discord-faint/20 animate-fade-in space-y-3">
          {/* Hook text */}
          <div className="bg-discord-input rounded-lg px-3 py-2.5 border-l-4 border-discord-blurple">
            <p className="text-discord-muted text-xs font-semibold mb-1 uppercase tracking-wide">Hook</p>
            <p className="text-discord-white text-sm italic">"{vp.hookText}"</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-discord-input rounded-lg px-3 py-2">
              <p className="text-discord-muted text-xs font-semibold mb-1">Tone</p>
              <p className="text-discord-white text-sm">{vp.tone}</p>
            </div>
            <div className="bg-discord-input rounded-lg px-3 py-2">
              <p className="text-discord-muted text-xs font-semibold mb-1">Pacing</p>
              <p className="text-discord-white text-sm">{vp.pacing}</p>
            </div>
          </div>

          <div className="bg-discord-input rounded-lg px-3 py-2">
            <p className="text-discord-muted text-xs font-semibold mb-1">Structure</p>
            <p className="text-discord-white text-sm">{vp.structure}</p>
          </div>

          {vp.keyPhrases.length > 0 && (
            <div>
              <p className="text-discord-muted text-xs font-semibold mb-2">Key Phrases</p>
              <div className="flex flex-wrap gap-1.5">
                {vp.keyPhrases.map(kp => (
                  <Badge key={kp} color="cyan">{kp}</Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ProfileStat({ icon: Icon, label, value, color }) {
  return (
    <div className="flex items-start gap-3 p-3 bg-discord-input rounded-lg">
      <div className={`flex-shrink-0 mt-0.5 ${color}`}>
        <Icon size={16} />
      </div>
      <div className="min-w-0">
        <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-0.5">{label}</p>
        <p className="text-discord-white text-sm leading-snug">{value}</p>
      </div>
    </div>
  )
}

export default function ProfilePhase({ goToPhase, videoProfiles, creatorProfile }) {
  const [activeTab, setActiveTab] = useState('overall')

  if (!creatorProfile) {
    return (
      <div className="flex flex-col h-full bg-discord-bg items-center justify-center">
        <p className="text-discord-muted">No profile generated yet.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-discord-bg overflow-hidden animate-fade-in">
      <ChannelHeader icon="👤" name="creator-profile" topic="Your extracted style profile — per video and overall" />

      <div className="flex-1 overflow-y-auto px-6 py-6 max-w-3xl w-full mx-auto">
        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-discord-sidebar rounded-lg p-1">
          {[
            { key: 'overall', label: '✦ Overall Profile' },
            { key: 'videos',  label: `🎬 Per-Video (${videoProfiles.length})` },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`
                flex-1 py-2 px-4 rounded-md text-sm font-semibold transition-all duration-150
                ${activeTab === tab.key
                  ? 'bg-discord-blurple text-white shadow'
                  : 'text-discord-muted hover:text-discord-white'
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Overall Profile Tab */}
        {activeTab === 'overall' && (
          <div className="animate-slide-up space-y-5">
            {/* Niche banner */}
            <div className="flex items-center gap-4 p-5 bg-discord-sidebar rounded-xl border border-discord-blurple/30">
              <div className="flex items-center justify-center w-14 h-14 rounded-full bg-discord-blurple/20 flex-shrink-0">
                <User size={26} className="text-discord-blurple" />
              </div>
              <div>
                <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-1">Creator Niche</p>
                <p className="text-discord-white font-bold text-lg">{creatorProfile.creatorNiche}</p>
                <p className="text-discord-muted text-sm mt-1">{creatorProfile.targetAudience}</p>
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <ProfileStat icon={Zap} label="Dominant Tone" value={creatorProfile.dominantTone} color="text-discord-yellow" />
              <ProfileStat icon={Clock} label="Avg Pacing" value={creatorProfile.avgPacing} color="text-discord-green" />
              <ProfileStat icon={Target} label="Typical Structure" value={creatorProfile.typicalStructure} color="text-discord-blurple" />
              <ProfileStat icon={Repeat} label="Recurring Topics" value={creatorProfile.recurringTopics.join(', ')} color="text-purple-400" />
            </div>

            {/* Signature hooks */}
            <div className="p-4 bg-discord-sidebar rounded-lg border border-discord-faint/20">
              <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-3 flex items-center gap-1.5">
                <Zap size={13} /> Signature Hook Types
              </p>
              <div className="flex flex-wrap gap-2">
                {creatorProfile.signatureHooks.map(h => (
                  <Badge key={h} color="purple">{h}</Badge>
                ))}
              </div>
            </div>

            {/* Content style summary */}
            <div className="p-4 bg-discord-sidebar rounded-lg border border-discord-faint/20">
              <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-2 flex items-center gap-1.5">
                <MessageSquare size={13} /> Content Style Summary
              </p>
              <p className="text-discord-text text-sm leading-relaxed">{creatorProfile.contentStyleSummary}</p>
            </div>

            {/* Visual style */}
            <div className="p-4 bg-discord-sidebar rounded-lg border border-discord-faint/20">
              <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-3 flex items-center gap-1.5">
                <Film size={13} /> Visual Style Suggestions
              </p>
              <div className="flex flex-wrap gap-2">
                {creatorProfile.visualStyleSuggestions.map(s => (
                  <Badge key={s} color="cyan">{s}</Badge>
                ))}
              </div>
            </div>

            {/* CTA */}
            <button
              onClick={() => goToPhase(PHASES.IDEATION)}
              className="
                flex items-center justify-center gap-2 w-full
                px-6 py-4 rounded-lg mt-2
                bg-discord-blurple hover:bg-discord-blurple_hover
                text-white font-semibold text-base
                shadow-lg hover:shadow-discord-blurple/20 hover:shadow-xl
                transform hover:-translate-y-0.5
                transition-all duration-200
              "
            >
              Continue to Ideation
              <ChevronRight size={18} />
            </button>
          </div>
        )}

        {/* Per-Video Tab */}
        {activeTab === 'videos' && (
          <div className="animate-slide-up space-y-3">
            <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-4">
              Click any video to expand its style profile
            </p>
            {videoProfiles.map((vp, i) => (
              <VideoProfileCard key={vp.id} vp={vp} index={i} />
            ))}
            <button
              onClick={() => setActiveTab('overall')}
              className="
                flex items-center justify-center gap-2 w-full mt-4
                px-6 py-3 rounded-lg
                bg-discord-sidebar hover:bg-discord-hover
                text-discord-muted hover:text-discord-white font-medium text-sm
                border border-discord-faint/30 hover:border-discord-faint/60
                transition-all duration-200
              "
            >
              View Overall Profile →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
