// ─────────────────────────────────────────────────────────────────────────────
// VIRALHOOK — CENTRALIZED MOCK DATA
// All mock content lives here. Replace with real API responses later.
// ─────────────────────────────────────────────────────────────────────────────

import PREMIERE_XML from './premiereXml.js'

export const NICHES = [
  'Tech', 'Finance', 'Fitness', 'Beauty', 'Gaming', 'Education', 'Personal Growth',
]

// ── Auth ─────────────────────────────────────────────────────────────────────
export const MOCK_USERS = [
  { id: 'u1', email: 'demo@viralhook.ai', password: 'demo1234', name: 'Alex Rivera', handle: '@alexcreates' },
]

// ── Creator Profiles ─────────────────────────────────────────────────────────
export const MOCK_NEW_CREATOR_PROFILE = (formData) => ({
  id: 'cp_new_' + Date.now(),
  type: 'new',
  name: formData.name || 'Creator',
  handle: formData.handle || '@creator',
  niche: formData.niche || 'Tech',
  contentPreferences: formData.contentPreferences || '',
  dominantHookType: 'Curiosity Gap',
  dominantStructure: 'Hook → Context → Takeaway',
  styleSummary: 'Your profile has been initialised based on your niche and preferences. As you create more content, ViralHook will refine your style profile automatically.',
  analyzedVideos: 0, drafts: 0, scheduled: 0, published: 0,
})

export const MOCK_EXPERIENCED_CREATOR_PROFILE = (handle, niche) => ({
  id: 'cp_exp_' + Date.now(),
  type: 'experienced',
  name: handle.replace('@', '').replace(/\b\w/g, (c) => c.toUpperCase()),
  handle: handle.startsWith('@') ? handle : '@' + handle,
  niche: niche || 'Motivational self-improvement and personal growth',
  dominantHookType: 'Contrarian',
  dominantStructure: 'Hook → Explanation',
  styleSummary: 'The creator blends motivational messaging with quick, punchy hooks that challenge conventional thinking. They use a mix of inspirational and sarcastic tones, delivering content in a fast-paced format that keeps viewers engaged. Their videos often start with a provocative hook, followed by a concise explanation or solution, and end with a relatable takeaway. The voice is candid, direct, and occasionally humorous, making complex ideas accessible and memorable.',
  analyzedVideos: 3,
  drafts: 2,
  scheduled: 1,
  published: 14,
  pocNote: true,
  // Raw profile from creator_profile.json (Module 1 pipeline output)
  rawProfile: {
    creator_niche: 'Motivational self-improvement and personal growth with everyday life commentary',
    signature_hooks: ['Contrarian', 'Bold Claim', 'Curiosity Gap'],
    dominant_tone: 'Inspirational',
    avg_pacing: 'Fast-paced',
    typical_structure: 'Hook → Explanation',
    target_audience: 'Young adults (18-35) seeking motivation, personal growth, and relatable everyday life content',
    recurring_topics: ['Personal growth & self-comparison', 'Mortality & living fully', 'Daily life frustrations', 'Consistency & process', 'Motivational advice'],
    content_style_summary: 'The creator blends motivational messaging with quick, punchy hooks that challenge conventional thinking. They use a mix of inspirational and sarcastic tones, delivering content in a fast-paced format that keeps viewers engaged. Their videos often start with a provocative hook, followed by a concise explanation or solution, and end with a relatable takeaway. The voice is candid, direct, and occasionally humorous, making complex ideas accessible and memorable.',
    visual_style_suggestions: ['Fast cuts and quick transitions to match the fast pacing', 'On-screen text overlays highlighting key phrases for emphasis', 'Bright, energetic color palette to reinforce inspirational tone', 'Meme or sarcastic graphics inserted during humor beats for added relatability'],
  },
})

// ── Trending Topics ───────────────────────────────────────────────────────────
export const MOCK_TRENDING_TOPICS = [
  {
    id: 't1', topic: 'How AI Agents Are Changing Software Development', niche: 'Tech',
    trendScore: 87, creatorFit: 91,
    signals: ['Rising search interest in AI automation tools', 'Strong relevance to technology niche', 'Similar creator content averaged 2.3x normal reach', '4 top-performing videos on this topic last 7 days'],
    whyThis: 'Your audience consistently engages with AI-focused content. This topic sits at the intersection of developer tools and AI — a high-performing combination for your niche.',
  },
  {
    id: 't2', topic: 'The Quiet Death of Traditional SaaS', niche: 'Tech',
    trendScore: 79, creatorFit: 84,
    signals: ['Growing discourse around AI-native software models', 'High engagement on contrarian business takes', 'Underserved angle — few creators have covered this yet'],
    whyThis: 'Contrarian framing matches your dominant hook style. This topic gives you a clear "everyone thinks X, but Y" structure your audience responds to.',
  },
  {
    id: 't3', topic: 'Why Most Developers Are Learning the Wrong Things in 2025', niche: 'Tech',
    trendScore: 83, creatorFit: 88,
    signals: ['Developer education content trending upward', 'Strong emotional hook potential', 'Your past skill-advice content outperformed average by 1.8x'],
    whyThis: 'High personal relevance to your audience. The contrarian framing ("wrong things") maps directly to your signature hook style.',
  },
]

// ── Script Variants ───────────────────────────────────────────────────────────
export const MOCK_SCRIPT_VARIANTS = (topic) => [
  {
    id: 'sv_a', label: 'VARIANT A', topic,
    hook: '"Everyone thinks AI will replace programmers.\nThey\'re asking the wrong question."',
    hookType: 'Contrarian / Curiosity Gap',
    structure: 'Problem → Misconception → Explanation → Conclusion',
    styleConsistency: 91, hookAlignment: 88, structureAlignment: 94, overall: 91,
    scenes: buildScenes(topic, 'contrarian'),
  },
  {
    id: 'sv_b', label: 'VARIANT B', topic,
    hook: '"I spent 3 years fighting AI tools.\nHere\'s what changed my mind."',
    hookType: 'Story / Vulnerability',
    structure: 'Personal Story → Turning Point → Lesson → CTA',
    styleConsistency: 85, hookAlignment: 82, structureAlignment: 88, overall: 85,
    scenes: buildScenes(topic, 'story'),
  },
  {
    id: 'sv_c', label: 'VARIANT C', topic,
    hook: '"The developers who survive the next 5 years\nall have one thing in common."',
    hookType: 'Curiosity Gap / Bold Claim',
    structure: 'Hook → Evidence → Framework → Takeaway',
    styleConsistency: 78, hookAlignment: 80, structureAlignment: 75, overall: 78,
    scenes: buildScenes(topic, 'bold'),
  },
]

export const MOCK_FAILED_VARIANTS = (topic) => [
  {
    id: 'fv_a', label: 'VARIANT A', topic,
    hook: '"AI is changing software. Here is how."',
    hookType: 'Informational', structure: 'List format',
    styleConsistency: 48, hookAlignment: 42, structureAlignment: 55, overall: 48,
    failReason: 'Hook too generic — does not match creator contrarian style',
  },
  {
    id: 'fv_b', label: 'VARIANT B', topic,
    hook: '"In this video I will explain AI agents."',
    hookType: 'Descriptive', structure: 'Tutorial',
    styleConsistency: 38, hookAlignment: 35, structureAlignment: 50, overall: 40,
    failReason: 'Passive opening — low hook strength, inconsistent with creator voice',
  },
]

function buildScenes(topic, style) {
  const bases = {
    contrarian: [
      { id: 's1', startTime: '00:00', endTime: '00:03', segment: 'HOOK', voiceover: "AI won't replace developers. But developers who use AI will replace those who don't.", caption: 'AI WILL REPLACE DEVELOPERS?', shot: 'Close-up talking head', visual: 'Talking-head footage, direct eye contact' },
      { id: 's2', startTime: '00:03', endTime: '00:08', segment: 'SETUP', voiceover: "Everyone's debating whether AI takes our jobs. That's the wrong conversation entirely.", caption: 'WRONG QUESTION', shot: 'Medium shot', visual: 'B-roll: news headlines montage' },
      { id: 's3', startTime: '00:08', endTime: '00:15', segment: 'MAIN POINT', voiceover: 'The real shift is this: AI agents are turning solo developers into one-person engineering teams.', caption: 'ONE-PERSON TEAM', shot: 'Medium shot with gesture', visual: 'B-roll: developer coding with AI assistant' },
      { id: 's4', startTime: '00:15', endTime: '00:22', segment: 'EVIDENCE', voiceover: 'GitHub Copilot users ship 55% more code. Cursor users report finishing features in hours that used to take days.', caption: '55% MORE OUTPUT', shot: 'Cut to screen recording', visual: 'Screen: GitHub Copilot stats graphic' },
      { id: 's5', startTime: '00:22', endTime: '00:27', segment: 'CONCLUSION', voiceover: "The question isn't will AI replace you. It's are you using AI yet?", caption: 'ARE YOU USING AI?', shot: 'Close-up, direct camera', visual: 'Return to talking head, confident close' },
    ],
    story: [
      { id: 's1', startTime: '00:00', endTime: '00:04', segment: 'HOOK', voiceover: 'I spent 3 years refusing to use AI tools. Thought it was cheating.', caption: '3 YEARS OF RESISTANCE', shot: 'Close-up talking head', visual: 'Talking-head footage' },
      { id: 's2', startTime: '00:04', endTime: '00:09', segment: 'CONFLICT', voiceover: 'Then I watched a junior dev ship in one week what took me a month.', caption: 'THE MOMENT IT HIT', shot: 'Medium shot', visual: 'B-roll: time-lapse coding' },
      { id: 's3', startTime: '00:09', endTime: '00:16', segment: 'TURNING POINT', voiceover: "I started using Cursor. Day one, I finished a feature I'd been stuck on for a week.", caption: 'ONE DAY CHANGED IT', shot: 'Screen recording', visual: 'Screen: Cursor IDE in use' },
      { id: 's4', startTime: '00:16', endTime: '00:22', segment: 'LESSON', voiceover: 'AI tools are not a shortcut. They are a multiplier for developers who already know what they are doing.', caption: 'MULTIPLIER NOT SHORTCUT', shot: 'Back to camera, medium', visual: 'Talking head with text animation' },
      { id: 's5', startTime: '00:22', endTime: '00:27', segment: 'CTA', voiceover: "If you're still avoiding AI tools, stop. Your competition isn't.", caption: 'STOP WAITING', shot: 'Close-up direct', visual: 'Final talking head, strong close' },
    ],
    bold: [
      { id: 's1', startTime: '00:00', endTime: '00:03', segment: 'HOOK', voiceover: 'The developers who survive the next 5 years all have one thing in common.', caption: 'ONE THING IN COMMON', shot: 'Close-up', visual: 'Talking head, strong framing' },
      { id: 's2', startTime: '00:03', endTime: '00:08', segment: 'BUILD-UP', voiceover: "It's not their language. Not their framework. Not their years of experience.", caption: "IT'S NOT WHAT YOU THINK", shot: 'Medium', visual: 'B-roll: code on screen, quick cuts' },
      { id: 's3', startTime: '00:08', endTime: '00:15', segment: 'REVEAL', voiceover: "They treat AI agents as collaborators. They don't just use AI, they direct it.", caption: 'THEY DIRECT AI', shot: 'Medium with whiteboard', visual: 'Simple diagram: Developer > AI Agent > Output' },
      { id: 's4', startTime: '00:15', endTime: '00:22', segment: 'FRAMEWORK', voiceover: 'Learn to write clear specs. Learn to review AI output critically. Learn to orchestrate, not just prompt.', caption: '3 SKILLS THAT MATTER', shot: 'List animation over talking head', visual: 'Text animation overlay' },
      { id: 's5', startTime: '00:22', endTime: '00:27', segment: 'CTA', voiceover: 'That is the skill gap. And right now, very few developers are filling it.', caption: 'FILL THE GAP', shot: 'Close-up direct close', visual: 'Final close, confident' },
    ],
  }
  return bases[style] || bases.contrarian
}

// ── Production Plan ───────────────────────────────────────────────────────────
export const MOCK_PRODUCTION_PLAN = (scriptVariant) => ({
  id: 'pp_' + Date.now(),
  title: scriptVariant?.topic || 'AI Agents & Software Development',
  totalDuration: '00:27',
  scenes: scriptVariant?.scenes || buildScenes('AI Agents', 'contrarian'),
})

// ── XML Export ────────────────────────────────────────────────────────────────
export const MOCK_XML_SUMMARY = {
  timeline: true, clips: 5, timestamps: true, clipOrdering: true,
  trimsAndCuts: true, captions: true, audioTracks: 1,
  transitions: 'Cross-dissolve between segments',
}

// Real Premiere Pro XMEML generated by ViralHook backend — validated in Premiere Pro
export const generateMockXML = (_plan) => PREMIERE_XML

// ── Video Timeline (AI Video screen) ─────────────────────────────────────────
export const MOCK_VIDEO_TIMELINE = (scenes) =>
  (scenes || buildScenes('AI Agents', 'contrarian')).map((sc) => ({
    ...sc,
    thumbnailBg: sceneColor(sc.segment),
  }))

function sceneColor(segment) {
  const map = {
    HOOK: '#5865F2', SETUP: '#3BA55C', 'MAIN POINT': '#FAA61A',
    EVIDENCE: '#ED4245', CONCLUSION: '#9C84EF', 'BUILD-UP': '#3BA55C',
    REVEAL: '#FAA61A', FRAMEWORK: '#ED4245', CTA: '#9C84EF',
    CONFLICT: '#FAA61A', 'TURNING POINT': '#3BA55C', LESSON: '#5865F2',
  }
  return map[segment] || '#4F545C'
}

// ── Mock visual assets for swap ───────────────────────────────────────────────
export const MOCK_VISUAL_ASSETS = [
  { id: 'va1', label: 'Talking Head - Direct', color: '#5865F2' },
  { id: 'va2', label: 'Screen Recording', color: '#3BA55C' },
  { id: 'va3', label: 'B-Roll: Coding Interface', color: '#FAA61A' },
  { id: 'va4', label: 'B-Roll: Data / Stats Graphic', color: '#ED4245' },
  { id: 'va5', label: 'Text Animation Overlay', color: '#9C84EF' },
  { id: 'va6', label: 'Split Screen', color: '#00B0F4' },
]

// ── Instagram / Publishing ────────────────────────────────────────────────────
export const MOCK_INSTAGRAM_ACCOUNT = {
  handle: '@alexcreates', connected: true, followers: '12.4K', avatar: 'AC',
}

export const MOCK_CAPTION = (topic) =>
  (topic || 'AI is changing software development') + ' and most developers are missing the shift.\n\nHere\'s what\'s actually happening\n\n#AI #SoftwareDevelopment #TechTrends #BuildInPublic #AIAgents'

export const CONTENT_STATUSES = ['Draft', 'Processing', 'Scheduled', 'Published', 'Failed']

// ── Dashboard content history ─────────────────────────────────────────────────
export const MOCK_CONTENT_HISTORY = [
  { id: 'h1', title: 'Why Most Developers Are Learning Wrong Things', status: 'Published', date: 'Aug 18', views: '24.1K', niche: 'Tech' },
  { id: 'h2', title: 'The Quiet Death of Traditional SaaS', status: 'Scheduled', date: 'Aug 27', views: '-', niche: 'Tech' },
  { id: 'h3', title: 'AI Agents Draft', status: 'Draft', date: 'Aug 25', views: '-', niche: 'Tech' },
]
