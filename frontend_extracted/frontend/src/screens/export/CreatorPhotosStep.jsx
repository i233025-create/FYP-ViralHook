import { useRef, useState } from 'react'
import { ImageOff, Check, Sparkles, RefreshCw, ArrowLeft } from 'lucide-react'
import { matchCreatorPhotos, photoUrl, uploadCreatorPhotos } from '../../services/api'
import { Btn, Card, Badge, Alert, Page, PageHero, ActionBar, SectionTitle, SegmentTag, Stat, Spinner } from '../../components/ui'

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
export default function CreatorPhotosStep({ plan, mode, review, setReview, choices, setChoices, onGenerate, onBack, topic }) {
  const fileRef = useRef(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)

  const addPhotos = async (fileList) => {
    const files = Array.from(fileList || []).filter((f) => f.type.startsWith('image/') || /\.jfif$/i.test(f.name))
    if (!files.length) return
    setError(null)
    try {
      setBusy('Uploading photos…')
      const { libraryId, photos } = await uploadCreatorPhotos(files)
      setBusy('Matching photos to scenes…')
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
  const nPhotos = Object.values(choices).filter(Boolean).length
  const planScenes = plan?.scenes || []

  return (
    <Page art="photos">
      {onBack && (
        <button type="button" onClick={onBack} className="mb-6 inline-flex items-center gap-1.5 text-[15px] font-semibold underline-offset-4 hover:underline">
          <ArrowLeft size={16} /> Back to preview
        </button>
      )}
      <PageHero
        step="04"
        label="AI video"
        title={['Your own', 'Shots']}
        topic={topic}
        lead="Optional. Upload photos of your products, places or events — each scene gets the best-fitting one, and you confirm or swap it before rendering."
      />

      {mode !== 'personalised' && (
        <div className="mb-5 max-w-3xl"><Alert type="info">Generic baseline mode ignores your photos — switch to Personalised to use them.</Alert></div>
      )}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        {/* drop zone */}
        <Card className="p-5 sm:p-6">
          <div
            role="button"
            tabIndex={0}
            onClick={() => !busy && fileRef.current?.click()}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && !busy && fileRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); addPhotos(e.dataTransfer.files) }}
            className={`flex min-h-[20rem] h-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-vh-night px-6 py-12 text-center transition-colors
              ${dragging ? 'bg-vh-accent/25' : 'bg-vh-cream hover:bg-vh-accent/10'}`}
          >
            <input ref={fileRef} type="file" accept="image/*,.jfif" multiple
              onChange={(e) => { addPhotos(e.target.files); e.target.value = '' }} />
            {busy
              ? <Spinner size={34} className="mb-5" />
              : <svg viewBox="0 0 60 60" className="mb-5 h-14 w-14" aria-hidden="true"><path d="M30 42 V10 M16 24 L30 10 L44 24 M10 52 H50" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" /></svg>}
            <p className="display text-[clamp(2.2rem,3.6vw,3rem)]">
              {busy || (review ? 'Replace photos' : 'Drop photos here')}
            </p>
            {!busy && <p className="mt-2 text-[17px]">or <span className="font-bold underline underline-offset-4">browse</span> from your device</p>}
            <p className="mt-3 font-mono text-[13px]">JPG, PNG or WEBP · up to 40 photos</p>
          </div>
        </Card>

        {/* scenes waiting for a photo */}
        <Card tone="dark" className="p-6 sm:p-8">
          <p className="font-mono text-[13px] font-semibold uppercase tracking-[0.08em] text-vh-accent">
            Scenes with your photos · {review ? `${nPhotos} / ${review.scenes.length}` : '—'}
          </p>
          <h2 className="display mt-3 text-[clamp(2.2rem,3.6vw,3rem)]">
            {review ? `${nPhotos} of ${review.scenes.length} scenes matched` : `${planScenes.length} scenes waiting`}
          </h2>
          <ol className="mt-5 space-y-3">
            {(review ? review.scenes.map((s) => ({ ...s, segment: s.segment || planScenes[s.index]?.segment })) : planScenes.map((s, i) => ({ ...s, index: i })))
              .map((s, i) => {
                const name = review ? choices[s.index] : null
                const photo = name && photoByName[name]
                return (
                  <li key={s.index ?? i} className="flex items-center gap-4">
                    {photo
                      ? <img src={photoUrl(photo.url)} alt="" className="h-14 w-12 shrink-0 rounded-md object-cover" />
                      : <span className="h-14 w-12 shrink-0 rounded-md border-2 border-dashed border-vh-cream/80" />}
                    <span className="display w-9 text-[2rem] text-vh-accent tabular">{String(i + 1).padStart(2, '0')}</span>
                    <span className="min-w-0 flex-1 truncate text-[17px] font-semibold capitalize">{(s.segment || `Scene ${i + 1}`).toLowerCase()}</span>
                    <span className="shrink-0 font-mono text-[13px]">{photo ? 'Your photo' : review ? 'Stock' : 'No photo yet'}</span>
                  </li>
                )
              })}
          </ol>
        </Card>
      </div>
      {error && <div className="mt-5"><Alert type="error">{error}</Alert></div>}

      {review && (
        <section className="mt-12">
          <SectionTitle right={
            <Btn size="sm" variant="secondary" icon={RefreshCw}
              onClick={() => setChoices(Object.fromEntries(review.scenes.map((s) => [s.index, s.suggested])))}>
              Reset to suggestions
            </Btn>
          }>
            One photo per scene
          </SectionTitle>
          <p className="-mt-2 mb-5 font-mono text-[13px]">{review.photos.length} photos · fit threshold {review.threshold}</p>
          <div className="space-y-4">
            {review.scenes.map((scene) => (
              <SceneReview key={scene.index} scene={scene} threshold={review.threshold}
                photoByName={photoByName} chosen={choices[scene.index] ?? null}
                usedElsewhere={new Set(Object.entries(choices).filter(([i, n]) => Number(i) !== scene.index && n).map(([, n]) => n))}
                onChoose={(name) => setChoices((c) => ({ ...c, [scene.index]: name }))} />
            ))}
          </div>
        </section>
      )}

      <ActionBar actions={<>
        <Btn variant="secondary" onClick={() => onGenerate(null)} disabled={!!busy}>
          {review ? 'Render without my photos' : 'Skip — no photos'}
        </Btn>
        {review && (
          <Btn size="lg" icon={Sparkles} disabled={!!busy}
            onClick={() => onGenerate({ libraryId: review.libraryId, sceneAssets: choices })}>
            Render video
          </Btn>
        )}
      </>}>
        <Stat label="Mode" value={mode === 'personalised' ? 'Personalised' : 'Generic baseline'} />
        <Stat label="Scenes with your photos" value={review ? `${nPhotos} / ${review.scenes.length}` : '—'} />
      </ActionBar>
    </Page>
  )
}

function SceneReview({ scene, threshold, photoByName, chosen, usedElsewhere, onChoose }) {
  const scoreOf = Object.fromEntries(scene.ranked.map((r) => [r.name, r.score]))
  const chosenScore = chosen ? scoreOf[chosen] : null
  const fits = chosenScore !== null && chosenScore !== undefined && chosenScore >= threshold

  return (
    <Card shadow={false} className="p-4 sm:p-5">
      <div className="flex items-start gap-4">
        <div className="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-xl border-2 border-vh-night bg-vh-cream">
          {chosen && photoByName[chosen]
            ? <img src={photoUrl(photoByName[chosen].url)} alt={chosen} className="h-full w-full object-cover" />
            : <ImageOff size={24} />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {scene.segment ? <SegmentTag segment={scene.segment} /> : <Badge>Scene {scene.index + 1}</Badge>}
            {chosen
              ? <Badge color={fits ? 'ok' : 'warn'}>{fits ? 'Good fit' : 'Below threshold'} · {fmt(chosenScore)}</Badge>
              : <Badge>Stock / generated visual</Badge>}
            {chosen && chosen === scene.suggested && <Badge color="accent">Suggested</Badge>}
            {chosen !== scene.suggested && <Badge color="pop">Your choice</Badge>}
          </div>
          <p className="mt-2 line-clamp-2 text-[15px]">{scene.clipIdea || '—'}</p>

          <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
            <button type="button" onClick={() => onChoose(null)} aria-pressed={chosen === null}
              className={`flex h-16 w-16 shrink-0 flex-col items-center justify-center gap-0.5 rounded-lg border-2 text-[11px] font-semibold
                ${chosen === null ? 'border-vh-night bg-vh-accent' : 'border-dashed border-vh-night hover:bg-vh-cream'}`}>
              <ImageOff size={15} />None
            </button>
            {scene.ranked.map((r) => {
              const photo = photoByName[r.name]
              if (!photo) return null
              const on = chosen === r.name
              return (
                <button key={r.name} type="button" onClick={() => onChoose(r.name)} aria-pressed={on}
                  title={`${r.name} · fit ${fmt(r.score)}`}
                  className={`relative h-16 w-16 shrink-0 overflow-hidden rounded-lg border-[3px]
                    ${on ? 'border-vh-accent' : 'border-transparent hover:border-vh-night'}
                    ${r.score !== null && r.score < threshold ? 'opacity-55' : ''}`}>
                  <img src={photoUrl(photo.url)} alt={r.name} className="h-full w-full object-cover" />
                  <span className="absolute inset-x-0 bottom-0 bg-vh-night/85 text-center font-mono text-[9px] text-vh-cream">
                    {fmt(r.score)}{usedElsewhere.has(r.name) ? ' · used' : ''}
                  </span>
                  {on && <Check size={13} strokeWidth={3} className="absolute right-0.5 top-0.5 rounded-full bg-vh-accent text-vh-ink" />}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </Card>
  )
}
