import { useState, useRef } from 'react'
import { Upload, Film, X, CheckCircle, AlertCircle, ChevronRight, Plus } from 'lucide-react'
import { PHASES } from '../phases'
import ChannelHeader from './ChannelHeader'
import LoadingDots from './LoadingDots'

export default function UploadPhase({
  goToPhase,
  uploadedVideos, setUploadedVideos,
  setVideoProfiles, setCreatorProfile,
}) {
  const fileInputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState(null)

  // --- Helpers ---
  const formatSize = (bytes) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const addFiles = (fileList) => {
    const newFiles = Array.from(fileList)
      .filter(f => f.type.startsWith('video/'))
      .map(f => ({ id: crypto.randomUUID(), file: f, name: f.name, size: f.size }))
    if (newFiles.length === 0) {
      setError('Please upload video files only (mp4, mov, etc.)')
      return
    }
    setError(null)
    setUploadedVideos(prev => [...prev, ...newFiles])
  }

  const removeVideo = (id) => setUploadedVideos(prev => prev.filter(v => v.id !== id))

  // --- Mock profile generation ---
  const generateProfile = async () => {
    if (uploadedVideos.length === 0) return
    setGenerating(true)
    setError(null)

    // Simulate async processing delay (1.5s per video)
    await new Promise(r => setTimeout(r, 1500 + uploadedVideos.length * 800))

    // Mock per-video profiles based on uploaded filenames
    const mockVideoProfiles = uploadedVideos.map((v, i) => ({
      id: v.id,
      videoName: v.name,
      topic: ['Personal Development', 'Motivation', 'Mindset Shift', 'Productivity Hacks', 'Success Secrets'][i % 5],
      hookText: [
        'Nobody tells you this about success...',
        'Stop doing this one thing if you want to grow...',
        'The biggest lie they told you about productivity',
        'You\'ve been thinking about goals all wrong',
        'This 2-minute habit changed everything for me',
      ][i % 5],
      hookType: ['Curiosity Gap', 'Contrarian', 'Bold Claim', 'Problem-Agitate', 'Story'][i % 5],
      tone: 'Conversational',
      pacing: 'Fast-paced',
      structure: 'Hook → Explanation → CTA',
      keyPhrases: ['consistency beats talent', 'the compound effect', 'discipline equals freedom'].slice(0, 2 + (i % 2)),
    }))

    const mockCreatorProfile = {
      creatorNiche: 'Personal Development & Motivational Content',
      signatureHooks: ['Curiosity Gap', 'Contrarian', 'Bold Claim'],
      dominantTone: 'Conversational',
      avgPacing: 'Fast-paced',
      typicalStructure: 'Hook → Explanation (sometimes Problem → Solution)',
      targetAudience: '18–34 year olds seeking self-improvement',
      recurringTopics: ['mindset', 'productivity', 'discipline', 'success habits'],
      contentStyleSummary: 'Short punchy openers that challenge conventional wisdom, followed by concise practical takeaways. Uses first-person storytelling with direct address ("you"). Ends with a motivational one-liner or soft CTA.',
      visualStyleSuggestions: ['Clean black/white text animations', 'Fast B-roll cuts', 'Subtle zoom transitions'],
    }

    setVideoProfiles(mockVideoProfiles)
    setCreatorProfile(mockCreatorProfile)
    setGenerating(false)
    goToPhase(PHASES.PROFILE)
  }

  // --- Drag & drop handlers ---
  const onDragOver  = (e) => { e.preventDefault(); setDragOver(true) }
  const onDragLeave = ()  => setDragOver(false)
  const onDrop      = (e) => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files) }

  return (
    <div className="flex flex-col h-full bg-discord-bg overflow-hidden animate-fade-in">
      <ChannelHeader icon="📁" name="upload-videos" topic="Upload your existing short-form videos to extract your creator style" />

      <div className="flex-1 overflow-y-auto px-6 py-6 max-w-3xl w-full mx-auto">
        {/* Drop zone */}
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          className={`
            relative flex flex-col items-center justify-center
            border-2 border-dashed rounded-xl p-12 mb-6 cursor-pointer
            transition-all duration-200 select-none
            ${dragOver
              ? 'border-discord-blurple bg-discord-blurple/10 scale-[1.01]'
              : 'border-discord-faint hover:border-discord-muted hover:bg-discord-sidebar/50 bg-discord-sidebar/30'
            }
          `}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            multiple
            onChange={e => addFiles(e.target.files)}
          />
          <div className="flex items-center justify-center w-16 h-16 rounded-full bg-discord-blurple/15 mb-4">
            <Upload size={28} className="text-discord-blurple" />
          </div>
          <p className="text-discord-white font-semibold text-base mb-1">
            {dragOver ? 'Drop your videos here' : 'Drop videos here, or click to browse'}
          </p>
          <p className="text-discord-muted text-sm">Supports MP4, MOV, AVI, MKV</p>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 px-4 py-3 mb-4 bg-discord-red/15 border border-discord-red/30 rounded-lg text-discord-red text-sm animate-fade-in">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {/* Uploaded video list */}
        {uploadedVideos.length > 0 && (
          <div className="space-y-2 mb-6 animate-slide-up">
            <div className="flex items-center justify-between mb-3">
              <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide">
                Queued Videos — {uploadedVideos.length}
              </p>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-1 text-discord-blurple hover:text-discord-white text-xs font-medium transition-colors"
              >
                <Plus size={14} /> Add more
              </button>
            </div>

            {uploadedVideos.map((v) => (
              <div
                key={v.id}
                className="flex items-center gap-3 px-4 py-3 bg-discord-sidebar rounded-lg border border-discord-faint/20 hover:border-discord-faint/40 transition-colors group"
              >
                <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-discord-blurple/15 flex-shrink-0">
                  <Film size={18} className="text-discord-blurple" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-discord-white text-sm font-medium truncate">{v.name}</p>
                  <p className="text-discord-muted text-xs">{formatSize(v.size)}</p>
                </div>
                <CheckCircle size={16} className="text-discord-green flex-shrink-0 opacity-70" />
                <button
                  onClick={() => removeVideo(v.id)}
                  className="opacity-0 group-hover:opacity-100 text-discord-muted hover:text-discord-red transition-all p-1 rounded"
                >
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Generate Profile button */}
        {uploadedVideos.length > 0 && !generating && (
          <button
            onClick={generateProfile}
            className="
              flex items-center justify-center gap-2 w-full
              px-6 py-4 rounded-lg
              bg-discord-blurple hover:bg-discord-blurple_hover
              text-white font-semibold text-base
              shadow-lg hover:shadow-discord-blurple/20 hover:shadow-xl
              transform hover:-translate-y-0.5
              transition-all duration-200 animate-slide-up
            "
          >
            Generate Profile
            <ChevronRight size={18} />
          </button>
        )}

        {/* Loading state */}
        {generating && (
          <div className="flex flex-col items-center gap-4 py-8 animate-fade-in">
            <div className="flex gap-2">
              <span className="loading-dot" />
              <span className="loading-dot" />
              <span className="loading-dot" />
            </div>
            <div className="text-center">
              <p className="text-discord-white font-medium mb-1">Analysing your videos...</p>
              <p className="text-discord-muted text-sm">Transcribing, extracting style patterns, building your creator profile</p>
            </div>
          </div>
        )}

        {/* Empty hint */}
        {uploadedVideos.length === 0 && !generating && (
          <div className="text-center py-4">
            <p className="text-discord-muted text-sm">Upload at least 1 video to get started</p>
          </div>
        )}
      </div>
    </div>
  )
}
