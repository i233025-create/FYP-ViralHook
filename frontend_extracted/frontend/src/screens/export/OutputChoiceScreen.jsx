import { FileCode, Clock, FileVideo, Layers, Wand2, Pencil, Images } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { Page, PageHero, Badge } from '../../components/ui'
import { OptionCard, OptionGrid, PhonePreview, TimelinePreview } from '../../components/previews'

export default function OutputChoiceScreen() {
  const { navigate, selectedTopic, productionPlan } = useApp()
  const scenes = productionPlan?.scenes || []

  return (
    <Page art="output">
      <PageHero
        step="04"
        label="Output"
        title={['Choose a', 'Path']}
        topic={selectedTopic?.topic}
        lead="Take the plan into your own editor, or let ViralHook render the video for you."
      />

      <OptionGrid>
        <OptionCard
          number="01"
          kicker="A few seconds"
          title="Editable Premiere project"
          line="A ready-made timeline you finish in your own editor."
          preview={<TimelinePreview scenes={scenes} />}
          specs={[
            { icon: FileCode, label: 'Format', value: 'Premiere Pro XML' },
            { icon: Clock, label: 'Ready in', value: 'A few seconds' },
            { icon: Layers, label: 'You get', value: 'Clips, captions, voice slots' },
            { icon: Pencil, label: 'You do', value: 'Drop in your footage' },
          ]}
          bestFor="Creators who edit their own footage"
          onClick={() => navigate('xml-export')}
        />
        <OptionCard
          number="02"
          kicker="A few minutes"
          title="AI-rendered video"
          line="Voiced, cut to your pacing and captioned for you."
          badge={<Badge color="pop">Beta</Badge>}
          preview={<PhonePreview scenes={scenes} />}
          specs={[
            { icon: FileVideo, label: 'Format', value: 'MP4 · 9:16' },
            { icon: Clock, label: 'Ready in', value: 'A few minutes' },
            { icon: Images, label: 'Visuals', value: 'Your photos first' },
            { icon: Wand2, label: 'You do', value: 'Review scene by scene' },
          ]}
          bestFor="Posting fast without editing"
          onClick={() => navigate('video-gen')}
        />
      </OptionGrid>
    </Page>
  )
}
