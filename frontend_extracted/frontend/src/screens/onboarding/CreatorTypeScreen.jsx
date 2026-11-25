import { Clock, KeyRound, Film, Target } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { Page, PageHero, Badge } from '../../components/ui'
import { NichePreview, OptionCard, OptionGrid, ReelGridPreview, UploadPreview } from '../../components/previews'

export default function CreatorTypeScreen() {
  const { navigate, user } = useApp()
  const first = user?.name?.split(' ')[0]

  return (
    <Page art="onboarding" width="max-w-6xl">
      <PageHero
        label="Set up"
        title={['Welcome,', first || 'creator']}
        lead="ViralHook writes in your own voice, so it first needs to learn how you make videos. Choose how to start — you can change this later."
      />

      <OptionGrid cols={3}>
        <OptionCard
          number="01"
          kicker="About a minute"
          title="Connect Instagram"
          line="We import your reels and captions and learn your style from them."
          badge={<Badge color="muted">Coming soon</Badge>}
          preview={<ReelGridPreview />}
          specs={[
            { icon: Clock, label: 'Takes', value: 'About a minute' },
            { icon: KeyRound, label: 'You need', value: 'Business or Creator account' },
          ]}
          bestFor="Creators already posting reels"
          disabled
        />
        <OptionCard
          number="02"
          kicker="A few minutes"
          title="Upload your videos"
          line="Add a few past videos; we transcribe them and measure how you talk, hook and pace."
          badge={<Badge color="pop">Recommended</Badge>}
          preview={<UploadPreview />}
          specs={[
            { icon: Clock, label: 'Takes', value: 'A few minutes' },
            { icon: Film, label: 'You need', value: '3–10 of your videos' },
          ]}
          bestFor="The most accurate style match"
          cta="Upload"
          onClick={() => navigate('onboarding-experienced')}
        />
        <OptionCard
          number="03"
          kicker="30 seconds"
          title="I'm just starting"
          line="No videos yet? Pick your niche; style scores appear once you have videos."
          preview={<NichePreview />}
          specs={[
            { icon: Clock, label: 'Takes', value: '30 seconds' },
            { icon: Target, label: 'You need', value: 'Just your niche' },
          ]}
          bestFor="New creators"
          cta="Start"
          onClick={() => navigate('onboarding-new')}
        />
      </OptionGrid>
    </Page>
  )
}
