import { useState } from 'react'
import { ChevronRight, Zap, ArrowLeft, TrendingUp } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { Btn, Card, SectionHeader, Page } from '../../components/ui'

export default function TopicSelectScreen() {
  const { selectedTopic, setSelectedTopic, trendingTopics, navigate } = useApp()

  // Initialise picked from context (set by IdeationScreen when user clicked Select)
  // trendingTopics are the real fetched topics; fall back to selectedTopic if coming from own-idea path
  const topics = trendingTopics.length > 0 ? trendingTopics : (selectedTopic ? [selectedTopic] : [])

  const [picked, setPicked] = useState(selectedTopic)
  const [useOwn, setUseOwn] = useState(false)
  const [ownText, setOwnText] = useState('')

  const handleCardClick = (t) => {
    // Toggle: clicking the already-selected card unselects it
    setPicked(prev => prev?.id === t.id ? null : t)
  }

  const proceed = () => {
    if (!picked) return
    setSelectedTopic(picked)
    navigate('script')
  }

  return (
    <Page>
      <div className="max-w-2xl mx-auto">

        {/* Back button */}
        <button
          onClick={() => navigate('ideation')}
          className="flex items-center gap-1.5 text-discord-muted hover:text-discord-white text-sm mb-5 transition-colors"
        >
          <ArrowLeft size={15} /> Back to Ideation
        </button>

        <SectionHeader
          icon={Zap}
          title="Select your topic"
          subtitle="Choose the topic you want to create content around. Click a selected topic to deselect."
        />

        {/* Topic cards */}
        {!useOwn && topics.length > 0 && (
          <div className="space-y-3 mb-4">
            {topics.map((t) => (
              <Card
                key={t.id}
                selected={picked?.id === t.id}
                onClick={() => handleCardClick(t)}
                hoverable
                className="p-5 cursor-pointer"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <TrendingUp size={14} className="text-discord-blurple flex-shrink-0" />
                      <h4 className="text-discord-white font-semibold text-sm">{t.topic}</h4>
                    </div>
                    <div className="flex flex-wrap gap-3 mb-2">
                      <ScoreChip label="Trend Score" value={t.trendScore} />
                      <ScoreChip label="Creator Fit" value={t.creatorFit} />
                    </div>
                    <p className="text-discord-muted text-xs italic leading-relaxed mb-2">"{t.whyThis}"</p>
                    {t.signals?.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {t.signals.slice(0, 2).map((s, i) => (
                          <span key={i} className="text-discord-faint text-xs bg-discord-input px-2 py-0.5 rounded-full">• {s}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex-shrink-0 mt-0.5">
                    {picked?.id === t.id
                      ? <div className="w-6 h-6 rounded-full bg-discord-blurple flex items-center justify-center shadow-md"><span className="text-white text-xs">✓</span></div>
                      : <div className="w-6 h-6 rounded-full border-2 border-discord-faint/40" />}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* No topics yet — came directly without research */}
        {!useOwn && topics.length === 0 && (
          <div className="bg-discord-sidebar border border-discord-faint/20 rounded-xl p-6 mb-4 text-center">
            <p className="text-discord-muted text-sm">No trending topics loaded.</p>
            <p className="text-discord-faint text-xs mt-1">Go back and use "Find trending ideas" or enter your own idea below.</p>
          </div>
        )}

        {/* Own idea */}
        <div className="mb-6">
          {!useOwn ? (
            <button
              onClick={() => { setUseOwn(true); setPicked(null) }}
              className="text-discord-blurple text-sm hover:underline transition-colors"
            >
              + Use my own idea instead
            </button>
          ) : (
            <Card className="p-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-discord-white text-sm font-semibold">Your own idea</p>
                <button onClick={() => setUseOwn(false)} className="text-discord-muted hover:text-discord-white text-xs transition-colors">Cancel</button>
              </div>
              <input
                value={ownText}
                onChange={(e) => setOwnText(e.target.value)}
                placeholder="e.g. Why most developers are learning the wrong things"
                className="w-full bg-discord-input border border-discord-faint/40 rounded-lg px-3 py-2.5 text-discord-white text-sm placeholder-discord-muted/60 focus:outline-none focus:border-discord-blurple transition-colors"
                onKeyDown={(e) => { if (e.key === 'Enter' && ownText.trim()) { setPicked({ id: 'own_' + Date.now(), topic: ownText.trim(), trendScore: null, creatorFit: null, isOwn: true }); setUseOwn(false) } }}
              />
              <Btn
                className="mt-3 w-full"
                size="sm"
                variant="outline"
                disabled={!ownText.trim()}
                onClick={() => {
                  if (ownText.trim()) {
                    setPicked({ id: 'own_' + Date.now(), topic: ownText.trim(), trendScore: null, creatorFit: null, isOwn: true })
                    setUseOwn(false)
                  }
                }}
              >
                Use This Idea
              </Btn>
            </Card>
          )}
        </div>

        {/* Selected confirmation banner */}
        {picked && !useOwn && (
          <div className="bg-discord-blurple/10 border border-discord-blurple/30 rounded-xl p-4 mb-4 animate-fadeIn flex items-center justify-between">
            <div>
              <p className="text-discord-blurple text-xs font-semibold mb-0.5">Selected topic</p>
              <p className="text-discord-white text-sm font-medium">{picked.topic}</p>
            </div>
            <button
              onClick={() => setPicked(null)}
              className="text-discord-muted hover:text-discord-red text-xs transition-colors ml-4 flex-shrink-0"
            >
              ✕ Clear
            </button>
          </div>
        )}

        <Btn size="lg" className="w-full" disabled={!picked} onClick={proceed} icon={ChevronRight}>
          Generate Scripts
        </Btn>
      </div>
    </Page>
  )
}

function ScoreChip({ label, value }) {
  if (value == null) return null
  const color = value >= 85 ? 'text-discord-green' : value >= 70 ? 'text-discord-yellow' : 'text-discord-muted'
  return (
    <span className="text-xs">
      <span className="text-discord-faint">{label}: </span>
      <span className={`font-bold ${color}`}>{value}/100</span>
    </span>
  )
}
