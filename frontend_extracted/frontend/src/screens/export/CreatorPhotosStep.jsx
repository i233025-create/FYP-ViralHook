import { useRef, useState } from 'react'
import { Upload, ImageOff, Check, Sparkles, Images, RefreshCw } from 'lucide-react'
import { matchCreatorPhotos, photoUrl, uploadCreatorPhotos } from '../../services/api'
import { Btn, Card, Badge, Alert, SectionHeader, Page } from '../../components/ui'

const fmt = (s) => (s === null || s === undefined ? '—' : s.toFixed(3))

/**
 * Before rendering: the creator uploads their own photos (optional), SigLIP
 * suggests one per scene, and the creator confirms or swaps each choice.
 * Experiment E3 showed the similarity threshold alone mis-fires on related
 * photos (a ceremony photo for "convocation"), so the creator decides.
 *
 * review = { libraryId, threshold, photos, scenes }   (null until photos are matched)
 * choices = { [sceneIndex]: photoName | null }
 */
export default function CreatorPhotosStep({ plan, mode, review, setReview, choices, setChoices, onGenerate }) {
  const fileRef = useRef(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState(null)

  const addPhotos = async (fileList) => {
    const files = Array.from(fileList || []).filter((f) => f.type.startsWith('image/') || /\.jfif$/i.test(f.name))
    if (!files.length) return
    setError(null)
    try {
      setBusy('Uploading photos…')
      const { libraryId, photos } = await uploadCreatorPhotos(files)
      setBusy('Matching photos to scenes (SigLIP)…')
      const match = await matchCreatorPhotos({ libraryId, plan, photos })
      setReview({ libraryId, ...match })
      setChoices(Object.fromEntries(match.scenes.map((s) => [s.index, s.suggested])))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }

  const photoByName = Object.fromEntries((review?.photos || []).map((p) => [p.name, p]))
  const used = Object.values(choices).filter(Boolean)
  const nPhotos = used.length

  return (
    <Page>
      <div className="max-w-4xl mx-auto">
        <SectionHeader icon={Images} title="Your Photos"
          subtitle="Optional: upload your own photos (campus, products, events). Each scene gets the best-fitting photo; you confirm or swap it before the video is rendered." />

        {mode !== 'personalised' && (
          <div className="mt-4"><Alert type="info">Generic baseline mode ignores your photos — switch to Personalised to use them.</Alert></div>
        )}

        {/* Upload */}
        <Card className="p-4 mt-4">
          <div
            onClick={() => !busy && fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); addPhotos(e.dataTransfer.files) }}
            className="flex flex-col items-center justify-center border-2 border-dashed border-discord-faint/40 hover:border-discord-blurple/60 rounded-xl p-6 cursor-pointer transition-colors bg-discord-input/30 hover:bg-discord-blurple/5"
          >
            <input ref={fileRef} type="file" accept="image/*,.jfif" multiple className="hidden"
              onChange={(e) => { addPhotos(e.target.files); e.target.value = '' }} />
            <Upload size={22} className="text-discord-muted mb-2" />
            <p className="text-discord-white text-sm font-medium">
              {review ? 'Replace photos — drop or click to browse' : 'Drop photos or click to browse'}
            </p>
            <p className="text-discord-muted text-xs mt-1">JPG, PNG, WEBP — up to 40 photos</p>
          </div>
          {busy && <p className="text-discord-muted text-xs mt-3 animate-pulse">{busy}</p>}
          {error && <div className="mt-3"><Alert type="error">{error}</Alert></div>}
        </Card>

        {/* Review */}
        {review && (
          <>
            <div className="flex items-center justify-between mt-5 mb-2 flex-wrap gap-2">
              <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide">
                Review: photo per scene · {review.photos.length} photos · fit threshold {review.threshold}
              </p>
              <Btn size="sm" variant="ghost" icon={RefreshCw}
                onClick={() => setChoices(Object.fromEntries(review.scenes.map((s) => [s.index, s.suggested])))}>
                Reset to suggestions
              </Btn>
            </div>
            <div className="space-y-3">
              {review.scenes.map((scene) => (
                <SceneReview key={scene.index} scene={scene} threshold={review.threshold}
                  photoByName={photoByName} chosen={choices[scene.index] ?? null}
                  usedElsewhere={new Set(Object.entries(choices)
                    .filter(([i, n]) => Number(i) !== scene.index && n).map(([, n]) => n))}
                  onChoose={(name) => setChoices((c) => ({ ...c, [scene.index]: name }))} />
              ))}
            </div>
          </>
        )}

        <div className="flex gap-2 justify-end mt-5 flex-wrap">
          <Btn variant="secondary" onClick={() => onGenerate(null)} disabled={!!busy}>
            {review ? 'Generate without my photos' : 'Skip — no photos'}
          </Btn>
          {review && (
            <Btn icon={Sparkles} onClick={() => onGenerate({ libraryId: review.libraryId, sceneAssets: choices })}
              disabled={!!busy}>
              Generate video ({nPhotos} scene{nPhotos === 1 ? '' : 's'} with your photos)
            </Btn>
          )}
        </div>
      </div>
    </Page>
  )
}

function SceneReview({ scene, threshold, photoByName, chosen, usedElsewhere, onChoose }) {
  const scoreOf = Object.fromEntries(scene.ranked.map((r) => [r.name, r.score]))
  const chosenScore = chosen ? scoreOf[chosen] : null
  const fits = chosenScore !== null && chosenScore !== undefined && chosenScore >= threshold

  return (
    <Card className="p-3">
      <div className="flex items-start gap-3">
        {/* Current choice */}
        <div className="w-20 h-20 rounded-lg overflow-hidden flex-shrink-0 bg-discord-input flex items-center justify-center border border-discord-faint/30">
          {chosen && photoByName[chosen]
            ? <img src={photoUrl(photoByName[chosen].url)} alt={chosen} className="w-full h-full object-cover" />
            : <ImageOff size={22} className="text-discord-faint" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge color="muted">{scene.segment || `Scene ${scene.index + 1}`}</Badge>
            {chosen
              ? <Badge color={fits ? 'green' : 'yellow'}>
                  {fits ? 'fits' : 'below threshold'} · SigLIP {fmt(chosenScore)}
                </Badge>
              : <Badge color="muted">stock / generated visual</Badge>}
            {chosen === scene.suggested && chosen && <Badge color="blurple">suggested</Badge>}
            {chosen !== scene.suggested && <Badge color="purple">your choice</Badge>}
          </div>
          <p className="text-discord-text text-xs mt-1.5 line-clamp-2">{scene.clipIdea || '—'}</p>

          {/* Options: all photos ranked by fit, plus "none" */}
          <div className="flex gap-2 mt-2 overflow-x-auto pb-1">
            <button onClick={() => onChoose(null)}
              className={`flex-shrink-0 w-14 h-14 rounded-md flex flex-col items-center justify-center text-[10px] border
                ${chosen === null ? 'border-discord-blurple bg-discord-blurple/15 text-discord-white' : 'border-discord-faint/30 text-discord-muted hover:border-discord-faint/70'}`}>
              <ImageOff size={14} />none
            </button>
            {scene.ranked.map((r) => {
              const photo = photoByName[r.name]
              if (!photo) return null
              const selected = chosen === r.name
              return (
                <button key={r.name} onClick={() => onChoose(r.name)} title={`${r.name} · SigLIP ${fmt(r.score)}`}
                  className={`relative flex-shrink-0 w-14 h-14 rounded-md overflow-hidden border-2
                    ${selected ? 'border-discord-blurple' : 'border-transparent hover:border-discord-faint/70'}
                    ${r.score !== null && r.score < threshold ? 'opacity-60' : ''}`}>
                  <img src={photoUrl(photo.url)} alt={r.name} className="w-full h-full object-cover" />
                  <span className="absolute bottom-0 inset-x-0 bg-black/70 text-white text-[9px] text-center">
                    {fmt(r.score)}{usedElsewhere.has(r.name) ? ' · used' : ''}
                  </span>
                  {selected && <Check size={12} className="absolute top-0.5 right-0.5 text-white bg-discord-blurple rounded-full" />}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </Card>
  )
}
