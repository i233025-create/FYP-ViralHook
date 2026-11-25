import { MotionConfig } from 'framer-motion'
import { AppProvider, useApp } from './context/AppContext'
import { PageTransition } from './components/motion'
import AppShell from './components/AppShell'

// Screens
import AuthScreen               from './screens/auth/AuthScreen'
import { VerifyEmailScreen, ResetPasswordScreen, BootScreen } from './screens/auth/EmailLinkScreens'
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
import LandingScreen            from './screens/landing/LandingScreen'
import PricingScreen            from './screens/billing/PricingScreen'
import BillingScreen            from './screens/billing/BillingScreen'
import CheckoutDemoScreen       from './screens/billing/CheckoutDemoScreen'
import SettingsScreen           from './screens/settings/SettingsScreen'
import LibraryScreen            from './screens/library/LibraryScreen'

function Router() {
  const { screen } = useApp()

  const SCREEN_MAP = {
    'boot':                    <BootScreen />,
    'landing':                 <LandingScreen />,
    'auth':                    <AuthScreen />,
    'auth-signup':             <AuthScreen initialMode="signup" />,
    'pricing':                 <PricingScreen />,
    'billing':                 <BillingScreen />,
    'checkout-demo':           <CheckoutDemoScreen />,
    'settings':                <SettingsScreen />,
    'library':                 <LibraryScreen />,
    'library-scheduled':       <LibraryScreen initialFilter="Scheduled" />,
    'verify-email':            <VerifyEmailScreen />,
    'reset-password':          <ResetPasswordScreen />,
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
      <PageTransition screenKey={screen}>
        {SCREEN_MAP[screen] ?? <AuthScreen />}
      </PageTransition>
    </AppShell>
  )
}

export default function App() {
  return (
    // reducedMotion="user": no movement for people who turned motion off in their OS
    <MotionConfig reducedMotion="user">
      <AppProvider>
        <Router />
      </AppProvider>
    </MotionConfig>
  )
}
