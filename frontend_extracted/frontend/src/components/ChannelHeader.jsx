import { Hash } from 'lucide-react'

export default function ChannelHeader({ icon, name, topic }) {
  return (
    <div className="flex-shrink-0 flex items-center gap-3 px-4 h-12 bg-discord-bg border-b border-discord-faint/30 shadow-sm z-10">
      <div className="flex items-center gap-1.5 text-discord-white font-semibold text-sm">
        <span className="text-base">{icon}</span>
        <Hash size={15} className="text-discord-muted" />
        <span>{name}</span>
      </div>
      {topic && (
        <>
          <div className="w-px h-5 bg-discord-faint/50 mx-1" />
          <p className="text-discord-muted text-xs truncate hidden sm:block">{topic}</p>
        </>
      )}
    </div>
  )
}
