import { useEffect, useMemo, useState } from 'react'
import { Film, Plus, CalendarClock, Search } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { getContentHistory } from '../../services/api'
import { Btn, Card, EmptyState, Page, PageHero, Segmented } from '../../components/ui'
import { CountUp, Stagger, StaggerItem } from '../../components/motion'
import { ContentRow } from '../dashboard/DashboardScreen'

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'Published', label: 'Published' },
  { value: 'Draft', label: 'Drafts' },
  { value: 'Scheduled', label: 'Scheduled' },
]

export default function LibraryScreen({ initialFilter = 'all' }) {
  const { navigate } = useApp()
  const [items, setItems] = useState([])
  const [filter, setFilter] = useState(initialFilter)
  const [query, setQuery] = useState('')

  useEffect(() => { getContentHistory().then(({ history }) => setItems(history)).catch(() => setItems([])) }, [])

  const shown = useMemo(() => items.filter((i) =>
    (filter === 'all' || i.status === filter) && i.title.toLowerCase().includes(query.trim().toLowerCase())), [items, filter, query])
  const count = (status) => items.filter((i) => i.status === status).length
  const scheduled = filter === 'Scheduled'

  return (
    <Page art="library">
      <PageHero
        label={scheduled ? 'Scheduled' : 'Library'}
        title={scheduled ? ['Coming', 'Up'] : ['My', 'Content']}
        lead={scheduled ? 'Posts you scheduled from the Publish step, in date order.' : 'Every video you make, with its status. Search, filter, or start a new one.'}
        aside={<Btn size="lg" icon={Plus} onClick={() => navigate('ideation')}>New video</Btn>}
      />

      {/* counts on a black panel, as on the studio page */}
      <Card tone="dark" className="mb-10 p-5 sm:p-6">
        <Stagger as="dl" className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
          {[['All videos', items.length], ['Published', count('Published')], ['Scheduled', count('Scheduled')], ['Drafts', count('Draft')]].map(([label, v], i) => (
            <StaggerItem key={label} className={`flex min-h-[5.5rem] items-end justify-between rounded-xl px-4 pb-3 pt-2 text-vh-night ${i === 0 ? 'bg-vh-accent' : 'bg-vh-cream'}`}>
              <dt className="font-mono text-[13px]">{label}</dt>
              <dd className="display text-[3rem] leading-[0.8] tabular"><CountUp value={v} /></dd>
            </StaggerItem>
          ))}
        </Stagger>
      </Card>

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Segmented label="Filter" options={FILTERS} value={filter} onChange={setFilter} />
        <label className="relative w-full sm:w-72">
          <Search size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2" />
          <span className="sr-only">Search titles</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search titles"
            className="h-11 w-full rounded-xl border-2 border-vh-night bg-white pl-10 pr-3 text-[15px] placeholder:text-vh-night/45 focus:outline-none focus:ring-4 focus:ring-vh-accent/40" />
        </label>
      </div>

      {shown.length === 0 ? (
        <Card shadow={false}>
          <EmptyState icon={scheduled ? CalendarClock : Film}
            title={scheduled ? 'Nothing scheduled' : 'Nothing here yet'}
            action={<Btn variant="secondary" onClick={() => navigate('ideation')}>Start a video</Btn>}>
            {scheduled ? 'Posts you schedule from the Publish step appear here.' : 'Videos you make show up here with their status.'}
          </EmptyState>
        </Card>
      ) : (
        <Stagger as="ul" className="space-y-4">
          {shown.map((item) => <StaggerItem as="li" key={item.id}><ContentRow item={item} /></StaggerItem>)}
        </Stagger>
      )}
    </Page>
  )
}
