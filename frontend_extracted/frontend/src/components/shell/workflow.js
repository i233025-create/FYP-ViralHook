// The five steps of making a video, shared by the header stepper and the nav drawer.
// A step is unlocked once the previous one produced what it needs, and done once
// its own output exists.

export const WORKFLOW = [
  { key: 'idea',    label: 'Idea',    long: 'Ideation',        target: 'ideation',   screens: ['ideation', 'topic-select'] },
  { key: 'script',  label: 'Script',  long: 'Script',          target: 'script',     screens: ['script'] },
  { key: 'plan',    label: 'Plan',    long: 'Production plan', target: 'production', screens: ['production'] },
  { key: 'output',  label: 'Output',  long: 'Export / video',  target: 'output',     screens: ['output', 'xml-export', 'video-gen'] },
  { key: 'publish', label: 'Publish', long: 'Publish',         target: 'publish',    screens: ['publish'] },
]

/** State of every step for the current app state. */
export function workflowState(screen, app) {
  const { creatorProfile, selectedTopic, selectedVariant, productionPlan, exportXML, videoResult, publishStatus } = app
  const unlocked = {
    idea: !!creatorProfile,
    script: !!selectedTopic,
    plan: !!selectedVariant,
    output: !!productionPlan,
    publish: !!productionPlan,
  }
  const done = {
    idea: !!selectedTopic,
    script: !!selectedVariant,
    plan: !!productionPlan,
    output: !!(exportXML || videoResult),
    publish: !!publishStatus,
  }
  const currentIndex = WORKFLOW.findIndex((s) => s.screens.includes(screen))
  return WORKFLOW.map((s, i) => ({
    ...s,
    index: i,
    number: String(i + 1).padStart(2, '0'),
    current: i === currentIndex,
    unlocked: unlocked[s.key],
    done: done[s.key] && i !== currentIndex,
  }))
}

export const currentStepOf = (screen) => WORKFLOW.findIndex((s) => s.screens.includes(screen))
