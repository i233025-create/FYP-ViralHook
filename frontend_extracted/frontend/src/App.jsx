import { AppProvider, useApp } from './context/AppContext'
import AppShell from './components/AppShell'

// Screens
import AuthScreen               from './screens/auth/AuthScreen'
import CreatorTypeScreen        from './screens/onboarding/CreatorTypeScreen'
import NewCreatorScreen         from './screens/onboarding/NewCreatorScreen'
import ExperiencedCreatorScreen from './screens/onboarding/ExperiencedCreatorScreen'
import DashboardScreen          from './screens/dashboard/DashboardScreen'
import IdeationScreen           from './screens/ideation/IdeationScreen'
import TopicSelectScreen        from './screens/ideation/TopicSelectScreen'
import ScriptScreen             from './screens/script/ScriptScreen'
import ProductionScreen         from './screens/production/ProductionScreen'
import OutputChoiceScreen       from './screens/export/OutputChoiceScreen'
import XmlExportScreen          from './screens/export/XmlExportScreen'
import VideoGenScreen           from './screens/export/VideoGenScreen'
import PublishScreen            from './screens/publish/PublishScreen'

function Router() {
  const { screen } = useApp()

  const SCREEN_MAP = {
    'auth':                    <AuthScreen />,
    'creator-type':            <CreatorTypeScreen />,
    'onboarding-new':          <NewCreatorScreen />,
    'onboarding-experienced':  <ExperiencedCreatorScreen />,
    'dashboard':               <DashboardScreen />,
    'ideation':                <IdeationScreen />,
    'topic-select':            <TopicSelectScreen />,
    'script':                  <ScriptScreen />,
    'production':              <ProductionScreen />,
    'output':                  <OutputChoiceScreen />,
    'xml-export':              <XmlExportScreen />,
    'video-gen':               <VideoGenScreen />,
    'publish':                 <PublishScreen />,
  }

  return (
    <AppShell>
      {SCREEN_MAP[screen] ?? <AuthScreen />}
    </AppShell>
  )
}

export default function App() {
  return (
    <AppProvider>
      <Router />
    </AppProvider>
  )
}
