import { TabsList, TabsTrigger } from '@/components/ui/Tabs'
import { useSettingsStore } from '@/stores/settings'
import { useAuthStore } from '@/stores/state'
import { cn } from '@/lib/utils'
import { useTranslation } from 'react-i18next'
import {
  FileTextIcon,
  NetworkIcon,
  MessageSquareTextIcon,
  ShieldCheckIcon
} from 'lucide-react'

interface SidebarNavItemProps {
  value: string
  currentTab: string
  icon: React.ReactNode
  label: string
}

function SidebarNavItem({ value, currentTab, icon, label }: SidebarNavItemProps) {
  const active = currentTab === value
  return (
    <TabsTrigger
      value={value}
      className={cn(
        'flex w-full cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-all justify-start',
        active
          ? 'bg-emerald-400 text-zinc-50 shadow-sm'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      )}
    >
      {icon}
      <span className="truncate">{label}</span>
    </TabsTrigger>
  )
}

/**
 * Left navigation rail: the WebUI's primary feature entries. The active entry
 * drives the Radix `Tabs` value so it stays in sync with the persisted
 * `currentTab` setting, while the right side renders the matching content.
 */
export default function Sidebar() {
  const currentTab = useSettingsStore.use.currentTab()
  const { isGuestMode } = useAuthStore()
  const { t } = useTranslation()

  return (
    <aside className="border-border/40 bg-background/60 flex w-56 shrink-0 flex-col border-r">
      <TabsList className="flex h-full w-full flex-col items-stretch justify-start gap-1 rounded-none p-3">
        <SidebarNavItem
          value="documents"
          currentTab={currentTab}
          icon={<FileTextIcon className="size-4 shrink-0" aria-hidden="true" />}
          label={t('header.documents')}
        />
        <SidebarNavItem
          value="knowledge-graph"
          currentTab={currentTab}
          icon={<NetworkIcon className="size-4 shrink-0" aria-hidden="true" />}
          label={t('header.knowledgeGraph')}
        />
        <SidebarNavItem
          value="retrieval"
          currentTab={currentTab}
          icon={<MessageSquareTextIcon className="size-4 shrink-0" aria-hidden="true" />}
          label={t('header.retrieval')}
        />
        {!isGuestMode && (
          <SidebarNavItem
            value="management"
            currentTab={currentTab}
            icon={<ShieldCheckIcon className="size-4 shrink-0" aria-hidden="true" />}
            label={t('header.administration')}
          />
        )}
      </TabsList>
    </aside>
  )
}
