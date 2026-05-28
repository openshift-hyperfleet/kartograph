<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { toast } from 'vue-sonner'
import {
  Cable,
  Building2,
  Plus,
  ChevronRight,
  ChevronLeft,
  CheckCircle2,
  Loader2,
  Eye,
  EyeOff,
  Pencil,
  Check,
  X,
  Trash2,
  AlertTriangle,
  Lock,
  ScrollText,
  FileText,
  Settings,
  RefreshCw,
} from 'lucide-vue-next'
import {
  inferNameFromRepoUrl,
  validateStep1,
  validateStep2,
  buildDataSourceCreationUrl,
  buildDataSourceCreationBody,
} from '@/utils/dataSourceWizard'
import type { DetectedAdapterId } from '@/utils/dataSourceWizard'
import {
  validateTypeLabel,
  parsePropertyList,
  buildOntologySavePayload,
} from '@/utils/ontologyWizard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import SyncPhaseIndicator from '@/components/graph/SyncPhaseIndicator.vue'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { CopyableText } from '@/components/ui/copyable-text'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

// ── Types ──────────────────────────────────────────────────────────────────

interface SyncRun {
  id: string
  status: 'pending' | 'ingesting' | 'ai_extracting' | 'applying' | 'completed' | 'failed'
  started_at: string
  completed_at: string | null
  error: string | null
  token_usage_total?: number | null
  cost_total_usd?: number | null
  created_at: string
}

interface DataSourceItem {
  id: string
  name: string
  adapter_type: string
  knowledge_graph_id: string
  last_sync_at: string | null
  created_at: string
  last_extraction_baseline_commit?: string | null
  tracked_branch_head_commit?: string | null
  sync_runs?: SyncRun[]
  diff_summary?: DataSourceDiffSummary | null
}

interface DiffChangedFile {
  path: string
  status: string
}

interface DataSourceDiffSummary {
  baseline_commit: string | null
  tracked_head_commit: string | null
  total_changed_files: number
  added_count: number
  modified_count: number
  removed_count: number
  renamed_count: number
  files_truncated: boolean
  changed_files: DiffChangedFile[]
}

interface PendingSourceDraft {
  id: string
  url: string
  detectedAdapterId: DetectedAdapterId
  name: string
  branch: string
  nameError: string
  urlError: string
  branchError: string
}

interface SourceUrlInputRow {
  id: string
  url: string
}

interface ProposedNodeType {
  label: string
  description: string
  required_properties: string[]
  optional_properties: string[]
  editing: boolean
  // transient edit state
  editLabel: string
  editDescription: string
  editRequired: string
  editOptional: string
  editError?: string
}

interface ProposedEdgeType {
  label: string
  description: string
  from: string
  to: string
  required_properties: string[]
  optional_properties: string[]
  editing: boolean
  editLabel: string
  editDescription: string
  editRequired: string
  editOptional: string
  editError?: string
}

// ── Sync phase helpers ─────────────────────────────────────────────────────

/**
 * Map a backend sync-run status to a user-readable label.
 * The backend emits: pending, ingesting, ai_extracting, applying, completed, failed.
 * The value "running" is never emitted by the backend.
 */
function syncPhaseLabel(status: SyncRun['status']): string {
  const labels: Record<SyncRun['status'], string> = {
    pending:       'Pending',
    ingesting:     'Ingesting',
    ai_extracting: 'Extracting',
    applying:      'Applying',
    completed:     'Completed',
    failed:        'Failed',
  }
  return labels[status] ?? status
}

function isActiveSyncPhase(status: SyncRun['status']): boolean {
  return status === 'pending' || status === 'ingesting' || status === 'ai_extracting' || status === 'applying'
}

// Statuses that indicate a sync is in progress and the page should poll.
const ACTIVE_STATUSES: SyncRun['status'][] = ['pending', 'ingesting', 'ai_extracting', 'applying']

// ── Composables ────────────────────────────────────────────────────────────

const { hasTenant, tenantVersion } = useTenant()

// ── Wizard state ───────────────────────────────────────────────────────────

const wizardOpen = ref(false)
const wizardStep = ref(1)
const WIZARD_STEPS = 2

// Step 1 – URL-first onboarding
const selectedKnowledgeGraphId = ref('')
const sourceUrlInputs = ref<SourceUrlInputRow[]>([{ id: 'source-1', url: '' }])
const sourceUrlError = ref('')
const providerError = ref('')
const pendingSources = ref<PendingSourceDraft[]>([])
const detectingSourceDetails = ref(false)
const knowledgeGraphs = ref<Array<{ id: string; name: string }>>([])
const loadingKgs = ref(false)

// Step 2 – Approval state
const connectingDataSource = ref(false)

// Step 2 – Connection configuration
const connToken = ref('')
const showToken = ref(false)
const connTokenError = ref('')

// ── GitHub ontology proposal ───────────────────────────────────────────────

const GITHUB_PROPOSAL_NODES: Omit<ProposedNodeType, 'editing' | 'editLabel' | 'editDescription' | 'editRequired' | 'editOptional'>[] = [
  {
    label: 'Repository',
    description: 'A GitHub repository containing code, issues, and pull requests.',
    required_properties: ['name', 'url'],
    optional_properties: ['description', 'stars', 'forks', 'default_branch'],
  },
  {
    label: 'Issue',
    description: 'An issue filed in a GitHub repository.',
    required_properties: ['title', 'number', 'state'],
    optional_properties: ['body', 'labels', 'closed_at'],
  },
  {
    label: 'PullRequest',
    description: 'A pull request proposing code changes.',
    required_properties: ['title', 'number', 'state'],
    optional_properties: ['body', 'base_branch', 'head_branch', 'merged_at'],
  },
  {
    label: 'Commit',
    description: 'A Git commit recorded in the repository.',
    required_properties: ['sha', 'message', 'timestamp'],
    optional_properties: ['author_email'],
  },
  {
    label: 'User',
    description: 'A GitHub user who interacts with the repository.',
    required_properties: ['login'],
    optional_properties: ['name', 'email', 'avatar_url'],
  },
]

const GITHUB_PROPOSAL_EDGES: Omit<ProposedEdgeType, 'editing' | 'editLabel' | 'editDescription' | 'editRequired' | 'editOptional'>[] = [
  {
    label: 'CONTAINS',
    description: 'A repository contains issues, pull requests, and commits.',
    from: 'Repository',
    to: 'Issue | PullRequest | Commit',
    required_properties: [],
    optional_properties: [],
  },
  {
    label: 'CREATED_BY',
    description: 'An issue or pull request was created by a user.',
    from: 'Issue | PullRequest',
    to: 'User',
    required_properties: [],
    optional_properties: ['created_at'],
  },
  {
    label: 'AUTHORED_BY',
    description: 'A commit was authored by a user.',
    from: 'Commit',
    to: 'User',
    required_properties: [],
    optional_properties: [],
  },
  {
    label: 'ASSIGNED_TO',
    description: 'An issue or pull request is assigned to a user.',
    from: 'Issue | PullRequest',
    to: 'User',
    required_properties: [],
    optional_properties: [],
  },
]

// ── Helpers ────────────────────────────────────────────────────────────────

function toProposedNode(n: typeof GITHUB_PROPOSAL_NODES[0]): ProposedNodeType {
  return {
    ...n,
    editing: false,
    editLabel: n.label,
    editDescription: n.description,
    editRequired: n.required_properties.join(', '),
    editOptional: n.optional_properties.join(', '),
  }
}

function toProposedEdge(e: typeof GITHUB_PROPOSAL_EDGES[0]): ProposedEdgeType {
  return {
    ...e,
    editing: false,
    editLabel: e.label,
    editDescription: e.description,
    editRequired: e.required_properties.join(', '),
    editOptional: e.optional_properties.join(', '),
  }
}

// ── URL detection & inference ───────────────────────────────────────────────

watch(sourceUrlInputs, () => {
  sourceUrlError.value = ''
  providerError.value = ''
}, { deep: true })

function addSourceInput(initialUrl = '') {
  sourceUrlInputs.value.push({
    id: `source-${Date.now()}-${sourceUrlInputs.value.length + 1}`,
    url: initialUrl,
  })
}

function removeSourceInput(id: string) {
  if (sourceUrlInputs.value.length === 1) {
    sourceUrlInputs.value[0]!.url = ''
    return
  }
  sourceUrlInputs.value = sourceUrlInputs.value.filter((entry) => entry.id !== id)
}

const sourceUrlPreviews = computed(() => {
  const seen = new Set<string>()
  const previews: Array<{ id: string; url: string; detectedAdapterId: DetectedAdapterId }> = []
  for (const row of sourceUrlInputs.value) {
    const url = row.url.trim()
    if (!url || seen.has(url)) continue
    seen.add(url)
    previews.push({
      id: row.id,
      url,
      detectedAdapterId: detectAdapterFromUrl(url),
    })
  }
  return previews
})

// ── Wizard navigation ──────────────────────────────────────────────────────

/**
 * Open the data source creation wizard, optionally pre-selecting a knowledge graph.
 *
 * @param preselectedKgId - When provided (e.g. from the ?kg_id= query param on
 *   the /data-sources route), the wizard opens with that KG already selected so
 *   the user can skip the KG selection step. This supports the post-KG-creation
 *   flow where the user is prompted to "Add Data Source" immediately after
 *   creating a new knowledge graph (task-101 / experience.spec.md).
 */
function openWizard(preselectedKgId?: string) {
  wizardStep.value = 1
  // Pre-select the knowledge graph if one was provided (e.g. from ?kg_id= query param).
  selectedKnowledgeGraphId.value = preselectedKgId ?? ''
  sourceUrlInputs.value = [{ id: 'source-1', url: '' }]
  sourceUrlError.value = ''
  providerError.value = ''
  pendingSources.value = []
  connectingDataSource.value = false
  detectingSourceDetails.value = false
  connToken.value = ''
  showToken.value = false
  connTokenError.value = ''
  wizardOpen.value = true
  loadKnowledgeGraphs()
}

function providerLabel(adapterId: DetectedAdapterId): string {
  if (adapterId === 'github') return 'GitHub'
  if (adapterId === 'gitlab') return 'GitLab'
  if (adapterId === 'jira') return 'Jira'
  return 'Unknown'
}

async function detectGithubSourceDetails(entry: PendingSourceDraft) {
  if (entry.detectedAdapterId !== 'github') return
  try {
    const parsed = new URL(entry.url)
    const [owner, repoRaw] = parsed.pathname.split('/').filter(Boolean)
    const repo = repoRaw?.replace(/\.git$/, '')
    if (!owner || !repo) return
    const response = await fetch(`https://api.github.com/repos/${owner}/${repo}`)
    if (!response.ok) return
    const payload = await response.json() as { default_branch?: string; name?: string }
    if (!entry.branch.trim() && payload.default_branch) {
      entry.branch = payload.default_branch
    }
    if (!entry.name.trim() && payload.name) {
      entry.name = payload.name
    }
  } catch {
    // Best effort only.
  }
}

async function detectGithubSourceDetailsBatch() {
  detectingSourceDetails.value = true
  try {
    for (const entry of pendingSources.value) {
      await detectGithubSourceDetails(entry)
    }
  } catch {
    // Best effort only; leave user-entered values untouched.
  } finally {
    detectingSourceDetails.value = false
  }
}

async function nextStep() {
  if (wizardStep.value === 1) {
    if (!selectedKnowledgeGraphId.value.trim()) {
      providerError.value = 'Select a knowledge graph to continue.'
      return
    }
    const parsedEntries = sourceUrlPreviews.value
    if (parsedEntries.length === 0) {
      sourceUrlError.value = 'Provide at least one source URL.'
      return
    }

    const drafts: PendingSourceDraft[] = parsedEntries.map((entry, index) => ({
      id: `src-${index}-${entry.url}`,
      url: entry.url,
      detectedAdapterId: entry.detectedAdapterId,
      name: inferNameFromRepoUrl(entry.url) ?? '',
      branch: '',
      nameError: '',
      urlError: '',
      branchError: '',
    }))

    let hasError = false
    const providerIssues: string[] = []
    for (const entry of drafts) {
      const validation = validateStep1({
        selectedKnowledgeGraphId: selectedKnowledgeGraphId.value,
        sourceUrl: entry.url,
        detectedAdapterId: entry.detectedAdapterId,
      })
      entry.urlError = validation.sourceUrlError
      if (validation.providerError) {
        providerIssues.push(`${entry.url}: ${validation.providerError}`)
      }
      if (!validation.valid) hasError = true
    }

    pendingSources.value = drafts
    sourceUrlError.value = hasError && drafts.some((d) => !!d.urlError)
      ? 'One or more URLs are invalid.'
      : ''
    providerError.value = providerIssues.join(' | ')
    if (hasError) return

    await detectGithubSourceDetailsBatch()
    wizardStep.value = 2
    return
  }

  if (wizardStep.value === 2) {
    let hasError = false
    for (const entry of pendingSources.value) {
      const validation = validateStep2({
        connName: entry.name,
        connRepoUrl: entry.url,
      })
      entry.nameError = validation.connNameError
      entry.urlError = validation.connRepoUrlError
      entry.branchError = !entry.branch.trim() ? 'Tracked branch is required.' : ''
      if (!validation.valid || entry.branchError) hasError = true
    }
    connTokenError.value = ''
    if (hasError) return
    await approveOntology()
    return
  }
}

function prevStep() {
  if (wizardStep.value > 1) wizardStep.value--
}

// ── Knowledge graph loader ─────────────────────────────────────────────────

async function loadKnowledgeGraphs() {
  loadingKgs.value = true
  try {
    const { apiFetch } = useApiClient()
    const result = await apiFetch<{ knowledge_graphs: Array<{ id: string; name: string }> }>(
      '/management/knowledge-graphs'
    )
    knowledgeGraphs.value = result.knowledge_graphs ?? []
  } catch {
    knowledgeGraphs.value = []
  } finally {
    loadingKgs.value = false
  }
}

// ── Data source API helpers ────────────────────────────────────────────────

async function createDataSource(params: {
  kg_id: string
  name: string
  adapter_type: string
  connection_config: Record<string, string>
  credentials?: Record<string, string>
}) {
  const { apiFetch } = useApiClient()
  return apiFetch(buildDataSourceCreationUrl(params.kg_id), {
    method: 'POST',
    body: buildDataSourceCreationBody({
      name: params.name,
      adapter_type: params.adapter_type,
      connection_config: params.connection_config,
      credentials: params.credentials,
    }),
  })
}

// ── Final approval ─────────────────────────────────────────────────────────

async function approveOntology() {
  if (!selectedKnowledgeGraphId.value) {
    toast.error('Please select a knowledge graph first')
    return
  }
  if (pendingSources.value.length === 0) {
    toast.error('Add at least one source URL first')
    return
  }

  connectingDataSource.value = true
  try {
    const failedEntries: Array<{ id: string; message: string }> = []
    let successCount = 0
    for (const entry of pendingSources.value) {
      try {
        await createDataSource({
          kg_id: selectedKnowledgeGraphId.value,
          name: entry.name,
          adapter_type: 'github',
          connection_config: {
            repo_url: entry.url,
            branch: entry.branch,
          },
          credentials: connToken.value ? { access_token: connToken.value } : undefined,
        })
        successCount += 1
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to connect source'
        failedEntries.push({ id: entry.id, message })
      }
    }

    if (successCount > 0) {
      await loadDataSources()
    }

    if (failedEntries.length === 0) {
      // Clear the plaintext token immediately after the API call succeeds so
      // that it does not linger in Vue's reactive state (readable via DevTools).
      connToken.value = ''
      toast.success('Data sources connected', {
        description: `${successCount} source(s) connected successfully.`,
      })
      wizardOpen.value = false
      return
    }

    pendingSources.value = pendingSources.value.filter((entry) =>
      failedEntries.some((failed) => failed.id === entry.id),
    )
    const firstError = failedEntries[0]?.message ?? 'Some sources failed to connect'
    if (successCount > 0) {
      toast.warning('Some sources were not connected', {
        description: `${successCount} succeeded, ${failedEntries.length} failed. ${firstError}`,
      })
    } else {
      toast.error('Connection failed', { description: firstError })
    }
    // Token is intentionally NOT cleared on partial/full failure so the user can retry.
  } finally {
    connectingDataSource.value = false
  }
}

// ── Sync monitoring state ──────────────────────────────────────────────────

const dataSources = ref<DataSourceItem[]>([])
const loadingDataSources = ref(false)
const scopedKnowledgeGraphId = ref('')
const manageReturnKgId = ref('')
const expandedDiffLists = ref<Record<string, boolean>>({})
const refreshingCommitRefs = ref<Record<string, boolean>>({})
const adoptingBaselines = ref<Record<string, boolean>>({})

function isMaintenanceReady(ds: DataSourceItem): boolean {
  if (!ds.last_extraction_baseline_commit || !ds.tracked_branch_head_commit) return false
  return ds.last_extraction_baseline_commit !== ds.tracked_branch_head_commit
}

const visibleDataSources = computed(() => {
  if (!scopedKnowledgeGraphId.value) return dataSources.value
  return dataSources.value.filter(
    (ds) => ds.knowledge_graph_id === scopedKnowledgeGraphId.value,
  )
})

const manageWorkspaceReturnUrl = computed(() =>
  manageReturnKgId.value
    ? `/knowledge-graphs/${manageReturnKgId.value}/manage`
    : '',
)

function isDiffExpanded(dsId: string): boolean {
  return expandedDiffLists.value[dsId] === true
}

function toggleDiffExpanded(dsId: string) {
  expandedDiffLists.value[dsId] = !isDiffExpanded(dsId)
}

async function refreshCommitRefs(dsId: string) {
  refreshingCommitRefs.value[dsId] = true
  try {
    const { apiFetch } = useApiClient()
    await apiFetch(`/management/data-sources/${dsId}/commit-refs/refresh`, {
      method: 'POST',
    })
    toast.success('Commit references refreshed')
    await loadDataSources()
  } catch {
    toast.error('Failed to refresh commit references')
  } finally {
    refreshingCommitRefs.value[dsId] = false
  }
}

async function adoptTrackedHeadBaseline(dsId: string) {
  adoptingBaselines.value[dsId] = true
  try {
    const { apiFetch } = useApiClient()
    await apiFetch(`/management/data-sources/${dsId}/commit-refs/adopt-tracked-head`, {
      method: 'POST',
    })
    toast.success('Baseline updated to tracked head')
    await loadDataSources()
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to update baseline'
    toast.error('Failed to update baseline', { description: msg })
  } finally {
    adoptingBaselines.value[dsId] = false
  }
}

async function loadDataSources() {
  if (!hasTenant.value) return
  loadingDataSources.value = true
  try {
    const { apiFetch } = useApiClient()
    // Fetch all knowledge graphs, then collect data sources for each.
    const kgResult = await apiFetch<{ knowledge_graphs: Array<{ id: string; name: string }> }>(
      '/management/knowledge-graphs'
    )
    const kgs = kgResult.knowledge_graphs ?? []
    const all: DataSourceItem[] = []
    for (const kg of kgs) {
      try {
        // Backend returns list[DataSourceResponse] as a direct JSON array.
        const sources = await apiFetch<DataSourceItem[]>(
          `/management/knowledge-graphs/${kg.id}/data-sources`
        )
        // Fetch sync runs for each data source so the card can show history.
        for (const ds of sources) {
          try {
            // Backend returns list[SyncRunResponse] as a direct JSON array.
            ds.sync_runs = (await apiFetch<SyncRun[]>(
              `/management/data-sources/${ds.id}/sync-runs`
            )) ?? []
          } catch {
            ds.sync_runs = []
          }
          try {
            ds.diff_summary = await apiFetch<DataSourceDiffSummary>(
              `/management/data-sources/${ds.id}/diff-summary`
            )
          } catch {
            ds.diff_summary = null
          }
          all.push(ds)
        }
      } catch {
        // Skip KGs whose data sources cannot be fetched.
      }
    }
    dataSources.value = all
  } catch {
    dataSources.value = []
  } finally {
    loadingDataSources.value = false
  }
}

// ── Sync polling ───────────────────────────────────────────────────────────

/**
 * True if at least one data source has a sync currently in progress.
 * Uses the most recent sync run (first in the array) as the source of truth.
 */
const hasActiveSyncs = computed(() =>
  dataSources.value.some((ds) => {
    const latestStatus = ds.sync_runs?.[0]?.status
    return latestStatus !== undefined && ACTIVE_STATUSES.includes(latestStatus)
  }),
)

/** Holds the active setInterval handle, or null when not polling. */
const pollInterval = ref<ReturnType<typeof setInterval> | null>(null)

/**
 * Clears the poll interval and resets the ref.
 * Safe to call when no interval is running.
 */
function stopPolling() {
  if (pollInterval.value !== null) {
    clearInterval(pollInterval.value)
    pollInterval.value = null
  }
}

/**
 * Starts polling every 5 seconds while any data source has an active sync.
 * Guards against starting a second interval if one is already running.
 * Automatically stops when all syncs reach a terminal state.
 */
function startPolling() {
  if (pollInterval.value !== null) return // already polling
  pollInterval.value = setInterval(async () => {
    await loadDataSources()
    if (!hasActiveSyncs.value) {
      stopPolling()
    }
  }, 3000)
}

onMounted(async () => {
  await loadDataSources()
  if (hasActiveSyncs.value) {
    startPolling()
  }
  // Cross-navigation from Schema Browser: open ontology editor for a specific type.
  const route = useRoute()
  const openOntologyType = route.query.openOntologyType as string | undefined
  if (openOntologyType && dataSources.value.length > 0) {
    // Open the first data source that contains the matching type label.
    // If no specific match, open the first data source as a fallback.
    const target = dataSources.value[0]
    if (target) {
      await nextTick()
      requestOntologyEdit(target)
    }
  }

  // Task-101: Post-KG-creation flow — auto-open wizard with new KG pre-selected.
  // When the user clicks "Add Data Source" from the post-KG-creation toast on
  // /knowledge-graphs, they are sent to /data-sources?kg_id=<new-kg-id>. Reading
  // this param here ensures the wizard opens immediately with the right KG chosen.
  // Manage workspace navigation contract: ?kg_id=<id>&from=manage preserves graph scope
  // without auto-opening the creation wizard (see buildDataSourcesStepUrl).
  const preselectedKgId = route.query.kg_id as string | undefined
  const fromManage = route.query.from === 'manage'

  if (fromManage && preselectedKgId) {
    scopedKnowledgeGraphId.value = preselectedKgId
    manageReturnKgId.value = preselectedKgId
  } else if (preselectedKgId) {
    await nextTick()
    openWizard(preselectedKgId)
  }
})

onUnmounted(() => {
  // Always clear the poll interval to prevent memory leaks when navigating away.
  stopPolling()
})

// Reload data sources whenever the user switches tenants.
watch(tenantVersion, () => {
  // Clear stale data immediately so old tenant's sources are not shown during load
  dataSources.value = []
  loadDataSources()
})

async function triggerSync(dsId: string) {
  try {
    const { apiFetch } = useApiClient()
    await apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
    toast.success('Sync triggered', { description: 'The data source sync has been initiated.' })
    await loadDataSources()
    // The newly triggered sync is now active — start polling if not already running.
    if (hasActiveSyncs.value) {
      startPolling()
    }
  } catch {
    toast.error('Failed to trigger sync')
  }
}

// ── FAIL 2: Ontology edit after extraction (with confirmation gate) ─────────

// State for re-extraction confirmation dialog
const reExtractionConfirmOpen = ref(false)
const pendingOntologyEditDsId = ref<string | null>(null)

// State for the ontology edit dialog itself
const editOntologyOpen = ref(false)
const editingDataSource = ref<DataSourceItem | null>(null)
const editNodes = ref<ProposedNodeType[]>([])
const editEdges = ref<ProposedEdgeType[]>([])

function requestOntologyEdit(ds: DataSourceItem) {
  const hasCompletedExtraction = ds.sync_runs?.some((r) => r.status === 'completed') ?? false
  if (hasCompletedExtraction) {
    pendingOntologyEditDsId.value = ds.id
    reExtractionConfirmOpen.value = true
  } else {
    openOntologyEditor(ds)
  }
}

function confirmReExtraction() {
  reExtractionConfirmOpen.value = false
  const ds = dataSources.value.find((d) => d.id === pendingOntologyEditDsId.value)
  if (ds) openOntologyEditor(ds)
}

function cancelReExtraction() {
  reExtractionConfirmOpen.value = false
  pendingOntologyEditDsId.value = null
}

function openOntologyEditor(ds: DataSourceItem) {
  editingDataSource.value = ds
  // Pre-populate with the GitHub proposal as a stand-in for the stored ontology.
  // In a real implementation this would load from the server.
  editNodes.value = GITHUB_PROPOSAL_NODES.map(toProposedNode)
  editEdges.value = GITHUB_PROPOSAL_EDGES.map(toProposedEdge)
  editOntologyOpen.value = true
}

function closeOntologyEditor() {
  editOntologyOpen.value = false
  editingDataSource.value = null
  pendingOntologyEditDsId.value = null
  editNodes.value = []
  editEdges.value = []
}

// Saving state for the ontology editor Apply button
const savingOntology = ref(false)

async function saveOntology() {
  if (!editingDataSource.value) return
  savingOntology.value = true
  try {
    const { apiFetch } = useApiClient()
    // PATCH /management/data-sources/{ds_id} (flat endpoint per API conventions)
    await apiFetch(
      `/management/data-sources/${editingDataSource.value.id}`,
      {
        method: 'PATCH',
        body: buildOntologySavePayload(editNodes.value, editEdges.value),
      },
    )
    toast.success('Ontology saved', {
      description: 'The ontology has been updated. A full re-extraction will begin shortly.',
    })
    closeOntologyEditor()
    await loadDataSources()
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Failed to save ontology'
    toast.error('Failed to save ontology', { description: msg })
    // dialog stays open so user can retry
  } finally {
    savingOntology.value = false
  }
}

// ── Ontology editor dialog — type editing ─────────────────────────────────

function startEditNodeEditor(index: number) {
  const n = editNodes.value[index]
  n.editLabel = n.label
  n.editDescription = n.description
  n.editRequired = n.required_properties.join(', ')
  n.editOptional = n.optional_properties.join(', ')
  n.editError = ''
  n.editing = true
}

function saveEditNodeEditor(index: number) {
  const n = editNodes.value[index]
  const validation = validateTypeLabel(editNodes.value, n.editLabel, index)
  if (!validation.valid) {
    n.editError = validation.error
    return
  }
  n.editError = ''
  n.label = n.editLabel.trim()
  n.description = n.editDescription
  n.required_properties = parsePropertyList(n.editRequired)
  n.optional_properties = parsePropertyList(n.editOptional)
  n.editing = false
}

function cancelEditNodeEditor(index: number) {
  editNodes.value[index].editing = false
  editNodes.value[index].editError = ''
}

function removeNodeEditor(index: number) {
  editNodes.value.splice(index, 1)
}

function startEditEdgeEditor(index: number) {
  const e = editEdges.value[index]
  e.editLabel = e.label
  e.editDescription = e.description
  e.editRequired = e.required_properties.join(', ')
  e.editOptional = e.optional_properties.join(', ')
  e.editError = ''
  e.editing = true
}

function saveEditEdgeEditor(index: number) {
  const e = editEdges.value[index]
  const validation = validateTypeLabel(editEdges.value, e.editLabel, index)
  if (!validation.valid) {
    e.editError = validation.error
    return
  }
  e.editError = ''
  e.label = e.editLabel.trim()
  e.description = e.editDescription
  e.required_properties = parsePropertyList(e.editRequired)
  e.optional_properties = parsePropertyList(e.editOptional)
  e.editing = false
}

function cancelEditEdgeEditor(index: number) {
  editEdges.value[index].editing = false
  editEdges.value[index].editError = ''
}

function removeEdgeEditor(index: number) {
  editEdges.value.splice(index, 1)
}

function addEditNode() {
  editNodes.value.push({
    label: '',
    description: '',
    required_properties: [],
    optional_properties: [],
    editing: true,
    editLabel: '',
    editDescription: '',
    editRequired: '',
    editOptional: '',
  })
}

function addEditEdge() {
  editEdges.value.push({
    label: '',
    description: '',
    from: '',
    to: '',
    required_properties: [],
    optional_properties: [],
    editing: true,
    editLabel: '',
    editDescription: '',
    editRequired: '',
    editOptional: '',
  })
}

// ── FAIL 3: Sync Logs (View Logs per sync run) ────────────────────────────

const logSheetOpen = ref(false)
const selectedLogRunId = ref<string | null>(null)
const selectedLogDsId = ref<string | null>(null)
const runLogs = ref<string[]>([])
const logsLoading = ref(false)
const logsError = ref<string | null>(null)

async function viewLogs(ds: DataSourceItem, run: SyncRun) {
  selectedLogDsId.value = ds.id
  selectedLogRunId.value = run.id
  runLogs.value = []
  logsError.value = null
  logSheetOpen.value = true
  await fetchRunLogs(ds.id, run.id)
  await loadDataSources()
}

async function fetchRunLogs(dsId: string, runId: string) {
  logsLoading.value = true
  logsError.value = null
  try {
    const { apiFetch } = useApiClient()
    const result = await apiFetch<{ logs: string[] }>(
      `/management/data-sources/${dsId}/sync-runs/${runId}/logs`
    )
    runLogs.value = result.logs ?? []
  } catch (err) {
    logsError.value = err instanceof Error ? err.message : 'Failed to load logs'
    runLogs.value = []
  } finally {
    logsLoading.value = false
  }
}

function closeLogs() {
  logSheetOpen.value = false
  selectedLogRunId.value = null
  selectedLogDsId.value = null
  runLogs.value = []
  logsError.value = null
}

// ── task-081: Edit Config (connection-config update) ──────────────────────

const editConfigOpen = ref(false)
const editConfigDs = ref<DataSourceItem | null>(null)
const editConfigName = ref('')
const editConfigToken = ref('')
const editConfigNameError = ref('')
const savingConfig = ref(false)

function openEditConfig(ds: DataSourceItem) {
  editConfigDs.value = ds
  editConfigName.value = ds.name
  editConfigToken.value = '' // never pre-fill; credential is server-side only
  editConfigNameError.value = ''
  editConfigOpen.value = true
}

async function handleEditConfig() {
  editConfigNameError.value = ''
  if (!editConfigName.value.trim()) {
    editConfigNameError.value = 'Data source name is required'
    return
  }
  savingConfig.value = true
  try {
    const { apiFetch } = useApiClient()
    const body: Record<string, unknown> = { name: editConfigName.value.trim() }
    if (editConfigToken.value.trim()) {
      body.credentials = { access_token: editConfigToken.value.trim() }
    }
    // PATCH /management/data-sources/{ds_id} (flat endpoint per API conventions)
    await apiFetch(`/management/data-sources/${editConfigDs.value!.id}`, { method: 'PATCH', body })
    toast.success('Data source updated')
    editConfigOpen.value = false
    await loadDataSources()
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to update data source'
    toast.error('Failed to update data source', { description: msg })
    // sheet stays open so user can retry
  } finally {
    savingConfig.value = false
  }
}

// ── task-081: Delete Data Source ──────────────────────────────────────────

const deleteDsOpen = ref(false)
const deletingDs = ref<DataSourceItem | null>(null)
const deletingDsFlag = ref(false)

function openDeleteDs(ds: DataSourceItem) {
  deletingDs.value = ds
  deleteDsOpen.value = true
}

async function handleDeleteDs() {
  if (!deletingDs.value) return
  deletingDsFlag.value = true
  try {
    const { apiFetch } = useApiClient()
    // DELETE /management/data-sources/{ds_id} (flat endpoint per API conventions)
    await apiFetch(`/management/data-sources/${deletingDs.value.id}`, { method: 'DELETE' })
    const name = deletingDs.value.name
    toast.success(`Data source "${name}" deleted`)
    deleteDsOpen.value = false
    await loadDataSources()
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to delete data source'
    toast.error('Failed to delete data source', { description: msg })
    deleteDsOpen.value = false
  } finally {
    deletingDsFlag.value = false
    deletingDs.value = null
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="rounded-lg bg-primary/10 p-2">
          <Cable class="size-5 text-primary" />
        </div>
        <div>
          <h1 class="text-2xl font-semibold tracking-tight">Data Sources</h1>
          <p class="text-sm text-muted-foreground">
            Connect external data sources to your knowledge graphs for automated extraction
          </p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <Button
          v-if="manageWorkspaceReturnUrl"
          variant="outline"
          @click="navigateTo(manageWorkspaceReturnUrl)"
        >
          Back to workspace overview
        </Button>
        <Button :disabled="!hasTenant" @click="openWizard(scopedKnowledgeGraphId || undefined)">
          <Plus class="mr-2 size-4" />
          Add Data Source
        </Button>
      </div>
    </div>

    <Separator />

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view data sources.</p>
    </div>

    <template v-else>
      <Card>
        <CardHeader class="pb-2">
          <CardTitle class="text-sm">Data source catalog</CardTitle>
          <CardDescription class="text-xs">
            This page is optimized for source onboarding and source-level actions.
            Graph-wide run telemetry and maintenance controls live in the manage workspace.
          </CardDescription>
        </CardHeader>
      </Card>

      <!-- Empty state (no data sources yet) -->
      <div v-if="visibleDataSources.length === 0" class="flex flex-col items-center gap-4 py-16 text-center">
        <div class="rounded-full bg-muted p-5">
          <Cable class="size-10 text-muted-foreground" />
        </div>
        <div class="space-y-1">
          <h2 class="text-lg font-semibold">No data sources connected</h2>
          <p class="max-w-md text-sm text-muted-foreground">
            Add a data source to start importing data into your knowledge graph.
            Supported adapters fetch raw content which is then processed by the
            AI extraction pipeline to produce graph entities and relationships.
          </p>
        </div>
        <Button @click="openWizard">
          <Plus class="mr-2 size-4" />
          Add your first data source
        </Button>
      </div>

      <!-- Data source list (shown when sources exist) -->
      <div v-else class="space-y-3">
        <div v-for="ds in visibleDataSources" :key="ds.id" class="rounded-lg border bg-card">
          <div class="flex items-center justify-between p-4">
            <div class="flex items-center gap-3">
              <div class="rounded-md bg-muted p-2">
                <Cable class="size-4 text-muted-foreground" />
              </div>
              <div>
                <p class="font-medium text-sm">{{ ds.name }}</p>
                <p class="text-xs text-muted-foreground">{{ ds.adapter_type }}</p>
                <CopyableText :text="ds.id" label="Data source ID copied" class="mt-0.5" />
              </div>
            </div>
            <div class="flex items-center gap-2">
              <SyncPhaseIndicator
                v-if="ds.sync_runs?.[0]"
                :status="ds.sync_runs[0].status"
              />
              <Badge v-else variant="secondary" class="text-[10px]">Idle</Badge>
              <!-- Edit Ontology button (FAIL 2) -->
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button size="sm" variant="outline" @click="requestOntologyEdit(ds)">
                    <Pencil class="mr-1.5 size-3.5" />
                    Edit Ontology
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p v-if="ds.sync_runs?.some((r) => r.status === 'completed')">
                    Requires re-extraction confirmation
                  </p>
                  <p v-else>Edit the node and edge types for this data source</p>
                </TooltipContent>
              </Tooltip>
              <!-- Edit Config button (task-081) -->
              <Button size="sm" variant="outline" @click="openEditConfig(ds)">
                <Settings class="mr-1.5 size-3.5" />
                Edit Config
              </Button>
              <!-- Delete button (task-081) -->
              <Button
                size="sm"
                variant="outline"
                class="text-destructive hover:bg-destructive/10"
                @click="openDeleteDs(ds)"
              >
                <Trash2 class="mr-1.5 size-3.5" />
                Delete
              </Button>
              <Button size="sm" variant="outline" @click="triggerSync(ds.id)">
                Sync Now
              </Button>
            </div>
          </div>
          <!-- Commit status and diff summary cues -->
          <div class="border-t px-4 py-3">
            <p class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Commit Status</p>
            <div class="grid gap-2 sm:grid-cols-2">
              <div class="rounded-md border bg-muted/20 p-2">
                <p class="text-[10px] uppercase tracking-wider text-muted-foreground">Commit during last extraction</p>
                <p class="mt-1 font-mono text-xs break-all">{{ ds.last_extraction_baseline_commit ?? '—' }}</p>
              </div>
              <div class="rounded-md border bg-muted/20 p-2">
                <p class="text-[10px] uppercase tracking-wider text-muted-foreground">Tracked branch head commit</p>
                <p class="mt-1 font-mono text-xs break-all">{{ ds.tracked_branch_head_commit ?? '—' }}</p>
              </div>
            </div>
            <div class="mt-2 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                class="h-7 text-[10px]"
                :disabled="refreshingCommitRefs[ds.id] === true"
                @click="refreshCommitRefs(ds.id)"
              >
                <RefreshCw
                  class="mr-1 size-3"
                  :class="refreshingCommitRefs[ds.id] === true ? 'animate-spin' : ''"
                />
                {{ refreshingCommitRefs[ds.id] === true ? 'Refreshing…' : 'Refresh commits' }}
              </Button>
              <Button
                size="sm"
                variant="outline"
                class="h-7 text-[10px]"
                :disabled="adoptingBaselines[ds.id] === true || !isMaintenanceReady(ds)"
                @click="adoptTrackedHeadBaseline(ds.id)"
              >
                {{ adoptingBaselines[ds.id] === true ? 'Updating…' : 'Adopt tracked head as baseline' }}
              </Button>
            </div>

            <div
              v-if="ds.diff_summary"
              class="mt-3 rounded-md border p-2"
              :class="isMaintenanceReady(ds) ? 'border-amber-300 bg-amber-50/50 dark:border-amber-800 dark:bg-amber-950/20' : 'bg-muted/10'"
            >
              <div class="flex items-center justify-between gap-2">
                <div class="text-xs">
                  <span class="font-medium">{{ ds.diff_summary.total_changed_files }}</span>
                  changed files
                  (<span class="text-emerald-700 dark:text-emerald-400">+{{ ds.diff_summary.added_count }}</span>,
                  <span class="text-blue-700 dark:text-blue-400">~{{ ds.diff_summary.modified_count }}</span>,
                  <span class="text-rose-700 dark:text-rose-400">-{{ ds.diff_summary.removed_count }}</span>,
                  <span class="text-purple-700 dark:text-purple-400">r{{ ds.diff_summary.renamed_count }}</span>)
                </div>
                <Badge
                  :variant="isMaintenanceReady(ds) ? 'default' : 'secondary'"
                  class="text-[10px]"
                >
                  {{ isMaintenanceReady(ds) ? 'New commits available' : 'Up to date' }}
                </Badge>
              </div>

              <div class="mt-2 flex items-center justify-between">
                <p class="text-[11px] text-muted-foreground">
                  Changed-file list is collapsed by default for large diffs.
                </p>
                <Button
                  v-if="ds.diff_summary.changed_files.length > 0"
                  size="sm"
                  variant="ghost"
                  class="h-6 px-2 text-[10px]"
                  @click="toggleDiffExpanded(ds.id)"
                >
                  {{ isDiffExpanded(ds.id) ? 'Hide changed files' : 'Show changed files' }}
                </Button>
              </div>

              <div v-if="isDiffExpanded(ds.id) && ds.diff_summary.changed_files.length > 0" class="mt-2 space-y-1 rounded-md border bg-background/80 p-2">
                <div
                  v-for="file in ds.diff_summary.changed_files"
                  :key="`${file.status}:${file.path}`"
                  class="flex items-start justify-between gap-2 text-[11px]"
                >
                  <span class="font-mono break-all">{{ file.path }}</span>
                  <Badge variant="outline" class="h-5 text-[10px] uppercase">{{ file.status }}</Badge>
                </div>
                <p v-if="ds.diff_summary.files_truncated" class="pt-1 text-[10px] text-muted-foreground">
                  Showing first {{ ds.diff_summary.changed_files.length }} files. Refine or page for full list.
                </p>
              </div>
            </div>
          </div>
          <!-- Sync history -->
          <div v-if="ds.sync_runs && ds.sync_runs.length > 0" class="border-t px-4 py-3">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">Sync History</p>
            <div class="space-y-1">
              <div v-for="run in ds.sync_runs" :key="run.id" class="flex items-center gap-2 text-xs text-muted-foreground">
                <SyncPhaseIndicator :status="run.status" />
                <span>{{ new Date(run.started_at).toLocaleString() }}</span>
                <span v-if="run.completed_at">
                  ({{ Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000) }}s)
                </span>
                <span v-if="run.error" class="text-destructive">{{ run.error }}</span>
                <!-- View Logs button (FAIL 3) -->
                <Button
                  size="sm"
                  variant="ghost"
                  class="ml-auto h-6 px-2 text-[10px]"
                  @click="viewLogs(ds, run)"
                >
                  <ScrollText class="mr-1 size-3" />
                  View Logs
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ─── Add Data Source Wizard ─────────────────────────────────────── -->
    <Dialog v-model:open="wizardOpen">
      <DialogContent class="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add Data Source</DialogTitle>
          <DialogDescription>
            Connect an external data source to extract knowledge graph entities.
            Step {{ wizardStep }} of {{ WIZARD_STEPS }}.
          </DialogDescription>
        </DialogHeader>

        <!-- Step progress -->
        <div class="flex items-center gap-2 py-2">
          <template v-for="step in WIZARD_STEPS" :key="step">
            <div
              class="flex size-7 items-center justify-center rounded-full text-xs font-semibold transition-colors"
              :class="
                step < wizardStep
                  ? 'bg-primary text-primary-foreground'
                  : step === wizardStep
                    ? 'border-2 border-primary text-primary'
                    : 'border border-muted-foreground/30 text-muted-foreground'
              "
            >
              <CheckCircle2 v-if="step < wizardStep" class="size-4" />
              <span v-else>{{ step }}</span>
            </div>
            <div
              v-if="step < WIZARD_STEPS"
              class="h-px flex-1 transition-colors"
              :class="step < wizardStep ? 'bg-primary' : 'bg-muted'"
            />
          </template>
        </div>

        <!-- ── Step 1: Bulk URL entry ── -->
        <div v-if="wizardStep === 1" class="space-y-4">
          <div>
            <h3 class="text-sm font-semibold">Paste your source URLs</h3>
            <p class="text-xs text-muted-foreground">
              Add one source at a time with "Add another". We auto-detect provider and prepare all supported sources at once.
            </p>
          </div>

          <!-- Knowledge graph selection -->
          <div class="space-y-1.5">
            <Label>Knowledge Graph <span class="text-destructive">*</span></Label>
            <Select
              v-if="!loadingKgs && knowledgeGraphs.length > 0"
              v-model="selectedKnowledgeGraphId"
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a knowledge graph..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="kg in knowledgeGraphs" :key="kg.id" :value="kg.id">
                  {{ kg.name }}
                </SelectItem>
              </SelectContent>
            </Select>
            <div v-else-if="loadingKgs" class="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 class="size-4 animate-spin" /> Loading knowledge graphs...
            </div>
            <p v-else class="text-sm text-muted-foreground">
              No knowledge graphs found. <NuxtLink to="/knowledge-graphs" class="text-primary underline">Create one first</NuxtLink>.
            </p>
          </div>

          <div class="space-y-2">
            <Label>Data source URLs <span class="text-destructive">*</span></Label>
            <div
              v-for="(row, idx) in sourceUrlInputs"
              :key="row.id"
              class="rounded-md border p-2"
            >
              <div class="flex items-start gap-2">
                <Input
                  v-model="row.url"
                  :placeholder="`https://github.com/owner/repository-${idx + 1}`"
                />
                <Button
                  v-if="sourceUrlInputs.length > 1"
                  type="button"
                  variant="ghost"
                  size="sm"
                  class="h-9 shrink-0"
                  @click="removeSourceInput(row.id)"
                >
                  Remove
                </Button>
              </div>
              <div v-if="row.url.trim()" class="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                <span>Detected:</span>
                <Badge :variant="detectAdapterFromUrl(row.url) === 'github' ? 'default' : 'outline'">
                  {{ providerLabel(detectAdapterFromUrl(row.url)) }}
                </Badge>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <Button type="button" variant="outline" size="sm" @click="addSourceInput()">
                Add another
              </Button>
            </div>
            <p v-if="sourceUrlError" class="text-xs text-destructive">{{ sourceUrlError }}</p>
            <p
              v-if="providerError"
              class="text-xs"
              :class="providerError.includes('Unknown') ? 'text-destructive' : 'text-amber-600 dark:text-amber-400'"
            >
              {{ providerError }}
            </p>
            <p v-else class="text-xs text-muted-foreground">
              GitHub is fully supported now. GitLab and Jira are detected and shown as coming soon.
            </p>
          </div>

          <DialogFooter class="pt-2">
            <Button
              :disabled="!selectedKnowledgeGraphId || sourceUrlInputs.every((entry) => !entry.url.trim())"
              @click="nextStep"
            >
              Continue
              <ChevronRight class="ml-1 size-4" />
            </Button>
          </DialogFooter>
        </div>

        <!-- ── Step 2: Connection Configuration ── -->
        <div v-else-if="wizardStep === 2" class="space-y-5">
          <div>
            <h3 class="text-sm font-semibold">Confirm connection details</h3>
            <p class="text-xs text-muted-foreground">
              Review each detected source, adjust inferred name/branch if needed, then connect them all at once.
            </p>
          </div>

          <div class="space-y-3">
            <div
              v-for="entry in pendingSources"
              :key="entry.id"
              class="space-y-2 rounded-md border p-3"
            >
              <div class="flex items-center justify-between gap-2">
                <p class="text-xs font-mono break-all">{{ entry.url }}</p>
                <Badge variant="secondary">{{ providerLabel(entry.detectedAdapterId) }}</Badge>
              </div>
              <div class="grid gap-3 md:grid-cols-2">
                <div class="space-y-1.5">
                  <Label>Data Source Name <span class="text-destructive">*</span></Label>
                  <Input
                    v-model="entry.name"
                    placeholder="e.g. my-repository"
                    @input="entry.nameError = ''"
                  />
                  <p v-if="entry.nameError" class="text-xs text-destructive">{{ entry.nameError }}</p>
                </div>
                <div class="space-y-1.5">
                  <Label>Tracked Branch <span class="text-destructive">*</span></Label>
                  <Input
                    v-model="entry.branch"
                    placeholder="main"
                    @input="entry.branchError = ''"
                  />
                  <p v-if="entry.branchError" class="text-xs text-destructive">{{ entry.branchError }}</p>
                  <p v-else class="text-xs text-muted-foreground">Default branch is auto-detected when available.</p>
                </div>
              </div>
              <p v-if="entry.urlError" class="text-xs text-destructive">{{ entry.urlError }}</p>
            </div>
          </div>

          <div class="space-y-1.5">
            <Label for="ds-token">
              Access Token (optional)
            </Label>
            <div class="relative">
              <Input
                id="ds-token"
                v-model="connToken"
                :type="showToken ? 'text' : 'password'"
                placeholder="ghp_••••••••••••••••••••••••••••••••••••"
                class="pr-10"
                @input="connTokenError = ''"
              />
              <Button
                variant="ghost"
                size="icon"
                class="absolute right-1 top-1/2 size-7 -translate-y-1/2 text-muted-foreground"
                type="button"
                @click="showToken = !showToken"
              >
                <Eye v-if="!showToken" class="size-3.5" />
                <EyeOff v-else class="size-3.5" />
              </Button>
            </div>
            <p v-if="connTokenError" class="text-xs text-destructive">{{ connTokenError }}</p>
            <p v-else class="text-xs text-muted-foreground">
              A GitHub personal access token with <code class="rounded bg-muted px-0.5">read:repo</code> scope.
            </p>
          </div>

          <!-- Credential security note -->
          <div class="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/30">
            <Lock class="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" />
            <p class="text-xs text-amber-700 dark:text-amber-300">
              Credentials are encrypted server-side using Vault and are never stored in plain text.
              The token will not be retrievable after saving.
            </p>
          </div>

          <DialogFooter class="pt-2">
            <Button variant="outline" @click="prevStep">
              <ChevronLeft class="mr-1 size-4" />
              Back
            </Button>
            <Button :disabled="connectingDataSource || detectingSourceDetails" @click="nextStep">
              <Loader2 v-if="connectingDataSource || detectingSourceDetails" class="mr-1 size-4 animate-spin" />
              Add to project
            </Button>
          </DialogFooter>
        </div>

      </DialogContent>
    </Dialog>

    <!-- ─── FAIL 2: Re-extraction Confirmation Dialog ─────────────────────── -->
    <Dialog v-model:open="reExtractionConfirmOpen">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <AlertTriangle class="size-5 text-amber-500" />
            Confirm Re-extraction
          </DialogTitle>
          <DialogDescription>
            This data source has completed at least one extraction run. Modifying the ontology
            will trigger a <strong>full re-extraction</strong> of all data, which may take
            significant time depending on the data source size.
          </DialogDescription>
        </DialogHeader>
        <p class="text-sm text-muted-foreground">
          Are you sure you want to edit the ontology and trigger a re-extraction?
        </p>
        <DialogFooter class="pt-2">
          <Button variant="outline" @click="cancelReExtraction">
            Cancel
          </Button>
          <Button variant="destructive" @click="confirmReExtraction">
            <AlertTriangle class="mr-2 size-4" />
            Yes, Edit &amp; Re-extract
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ─── FAIL 2: Ontology Editor Dialog ────────────────────────────────── -->
    <Dialog v-model:open="editOntologyOpen">
      <DialogContent class="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Ontology — {{ editingDataSource?.name }}</DialogTitle>
          <DialogDescription>
            Modify node and edge types for this data source. Changes will be applied when you save.
          </DialogDescription>
        </DialogHeader>

        <!-- Node types -->
        <div class="space-y-2">
          <h4 class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Node Types ({{ editNodes.length }})
          </h4>
          <div class="space-y-2">
            <Card v-for="(node, idx) in editNodes" :key="idx" class="overflow-hidden">
              <CardContent v-if="!node.editing" class="flex items-start gap-3 p-3">
                <Badge variant="default" class="mt-0.5 shrink-0">Node</Badge>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium">{{ node.label }}</p>
                  <p class="text-xs text-muted-foreground">{{ node.description }}</p>
                  <div class="mt-1.5 flex flex-wrap gap-1">
                    <Badge v-for="prop in node.required_properties" :key="prop" variant="secondary" class="text-[10px]">
                      {{ prop }} <span class="ml-0.5 text-destructive">*</span>
                    </Badge>
                    <Badge v-for="prop in node.optional_properties" :key="prop" variant="outline" class="text-[10px]">
                      {{ prop }}
                    </Badge>
                  </div>
                </div>
                <div class="flex shrink-0 items-center gap-1">
                  <Button variant="ghost" size="icon" class="size-7" @click="startEditNodeEditor(idx)">
                    <Pencil class="size-3.5" />
                  </Button>
                  <Button variant="ghost" size="icon" class="size-7 text-destructive hover:text-destructive" @click="removeNodeEditor(idx)">
                    <Trash2 class="size-3.5" />
                  </Button>
                </div>
              </CardContent>
              <CardContent v-else class="space-y-3 p-3">
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1">
                    <Label class="text-xs">Label</Label>
                    <Input v-model="node.editLabel" class="h-8 text-xs" @input="node.editError = ''" />
                    <p v-if="node.editError" class="text-xs text-destructive">{{ node.editError }}</p>
                  </div>
                  <div class="space-y-1">
                    <Label class="text-xs">Description</Label>
                    <Input v-model="node.editDescription" class="h-8 text-xs" />
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1">
                    <Label class="text-xs">Required properties</Label>
                    <Input v-model="node.editRequired" placeholder="e.g. name, url" class="h-8 text-xs" />
                  </div>
                  <div class="space-y-1">
                    <Label class="text-xs">Optional properties</Label>
                    <Input v-model="node.editOptional" placeholder="e.g. description" class="h-8 text-xs" />
                  </div>
                </div>
                <div class="flex justify-end gap-2">
                  <Button variant="ghost" size="sm" class="h-7 text-xs" @click="cancelEditNodeEditor(idx)">
                    <X class="mr-1 size-3" /> Cancel
                  </Button>
                  <Button size="sm" class="h-7 text-xs" @click="saveEditNodeEditor(idx)">
                    <Check class="mr-1 size-3" /> Save
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
          <!-- Add Node Type button -->
          <Button variant="outline" size="sm" class="mt-2 w-full gap-2" @click="addEditNode">
            <Plus class="size-4" />
            Add Node Type
          </Button>
        </div>

        <!-- Edge types -->
        <div class="space-y-2 mt-4">
          <h4 class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Edge Types ({{ editEdges.length }})
          </h4>
          <div class="space-y-2">
            <Card v-for="(edge, idx) in editEdges" :key="idx" class="overflow-hidden">
              <CardContent v-if="!edge.editing" class="flex items-start gap-3 p-3">
                <Badge variant="outline" class="mt-0.5 shrink-0">Edge</Badge>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium font-mono">{{ edge.label }}</p>
                  <p class="text-xs text-muted-foreground">{{ edge.description }}</p>
                  <p class="text-xs text-muted-foreground/70 mt-0.5">{{ edge.from }} → {{ edge.to }}</p>
                </div>
                <div class="flex shrink-0 items-center gap-1">
                  <Button variant="ghost" size="icon" class="size-7 shrink-0" @click="startEditEdgeEditor(idx)">
                    <Pencil class="size-3.5" />
                  </Button>
                  <Button variant="ghost" size="icon" class="size-7 shrink-0 text-destructive hover:text-destructive" @click="removeEdgeEditor(idx)">
                    <Trash2 class="size-3.5" />
                  </Button>
                </div>
              </CardContent>
              <CardContent v-else class="space-y-3 p-3">
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1">
                    <Label class="text-xs">Label</Label>
                    <Input v-model="edge.editLabel" class="h-8 text-xs" @input="edge.editError = ''" />
                    <p v-if="edge.editError" class="text-xs text-destructive">{{ edge.editError }}</p>
                  </div>
                  <div class="space-y-1">
                    <Label class="text-xs">Description</Label>
                    <Input v-model="edge.editDescription" class="h-8 text-xs" />
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1">
                    <Label class="text-xs">From type</Label>
                    <Input v-model="edge.from" placeholder="e.g. Repository" class="h-8 text-xs" />
                  </div>
                  <div class="space-y-1">
                    <Label class="text-xs">To type</Label>
                    <Input v-model="edge.to" placeholder="e.g. Issue" class="h-8 text-xs" />
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1">
                    <Label class="text-xs">Required properties</Label>
                    <Input v-model="edge.editRequired" placeholder="comma-separated" class="h-8 text-xs" />
                  </div>
                  <div class="space-y-1">
                    <Label class="text-xs">Optional properties</Label>
                    <Input v-model="edge.editOptional" placeholder="comma-separated" class="h-8 text-xs" />
                  </div>
                </div>
                <div class="flex justify-end gap-2">
                  <Button variant="ghost" size="sm" class="h-7 text-xs" @click="cancelEditEdgeEditor(idx)">
                    <X class="mr-1 size-3" /> Cancel
                  </Button>
                  <Button size="sm" class="h-7 text-xs" @click="saveEditEdgeEditor(idx)">
                    <Check class="mr-1 size-3" /> Save
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
          <!-- Add Edge Type button -->
          <Button variant="outline" size="sm" class="mt-2 w-full gap-2" @click="addEditEdge">
            <Plus class="size-4" />
            Add Edge Type
          </Button>
        </div>

        <DialogFooter class="pt-4">
          <Button variant="outline" :disabled="savingOntology" @click="closeOntologyEditor">Cancel</Button>
          <Button :disabled="savingOntology" @click="saveOntology">
            <Loader2 v-if="savingOntology" class="mr-2 size-4 animate-spin" />
            {{ savingOntology ? 'Saving...' : 'Apply & Save' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ─── task-081: Edit Config Sheet ─────────────────────────────────── -->
    <Sheet v-model:open="editConfigOpen">
      <SheetContent side="right" class="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Edit Data Source</SheetTitle>
          <SheetDescription>
            Update the name or rotate the access credentials for this data source.
          </SheetDescription>
        </SheetHeader>
        <form class="mt-6 space-y-4" @submit.prevent="handleEditConfig">
          <div class="space-y-1.5">
            <Label for="edit-ds-name">Name <span class="text-destructive">*</span></Label>
            <Input
              id="edit-ds-name"
              v-model="editConfigName"
              placeholder="e.g. my-org/my-repo"
              :disabled="savingConfig"
              @input="editConfigNameError = ''"
            />
            <p v-if="editConfigNameError" class="text-sm text-destructive">{{ editConfigNameError }}</p>
          </div>
          <div class="space-y-1.5">
            <Label for="edit-ds-token">Access Token</Label>
            <Input
              id="edit-ds-token"
              v-model="editConfigToken"
              type="password"
              placeholder="Leave blank to keep existing credential"
              :disabled="savingConfig"
            />
            <p class="text-xs text-muted-foreground">
              The current credential is stored encrypted server-side and is never shown here.
              Enter a new token only if you need to rotate it.
            </p>
          </div>
          <div class="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              :disabled="savingConfig"
              @click="editConfigOpen = false"
            >
              Cancel
            </Button>
            <Button type="submit" :disabled="savingConfig || !editConfigName.trim()">
              <Loader2 v-if="savingConfig" class="mr-2 size-4 animate-spin" />
              {{ savingConfig ? 'Saving...' : 'Save' }}
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>

    <!-- ─── task-081: Delete Data Source AlertDialog ───────────────────── -->
    <AlertDialog v-model:open="deleteDsOpen">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete "{{ deletingDs?.name }}"?</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently delete the data source and all of its sync history.
            This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel :disabled="deletingDsFlag">Cancel</AlertDialogCancel>
          <AlertDialogAction
            class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            :disabled="deletingDsFlag"
            @click.prevent="handleDeleteDs"
          >
            <Loader2 v-if="deletingDsFlag" class="mr-2 size-4 animate-spin" />
            {{ deletingDsFlag ? 'Deleting...' : 'Delete' }}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>

    <!-- ─── FAIL 3: Sync Logs Sheet ───────────────────────────────────────── -->
    <Sheet v-model:open="logSheetOpen" @update:open="(v) => { if (!v) closeLogs() }">
      <SheetContent side="right" class="w-[42rem] max-w-[90vw] p-4">
        <SheetHeader>
          <SheetTitle class="flex items-center gap-2">
            <FileText class="size-4" />
            Sync Run Logs
          </SheetTitle>
          <SheetDescription>
            Detailed log output for sync run {{ selectedLogRunId }}
          </SheetDescription>
        </SheetHeader>

        <div class="mt-4 flex h-full flex-col gap-3">
          <!-- Loading -->
          <div v-if="logsLoading" class="flex flex-1 items-center justify-center">
            <Loader2 class="size-6 animate-spin text-muted-foreground" />
          </div>

          <!-- Error -->
          <div v-else-if="logsError" class="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {{ logsError }}
          </div>

          <!-- Empty -->
          <div v-else-if="runLogs.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 text-center text-muted-foreground">
            <ScrollText class="size-8" />
            <p class="text-sm">No log entries for this run.</p>
          </div>

          <!-- Log lines -->
          <div v-else class="flex-1 overflow-auto rounded-md border bg-muted/30 p-3">
            <pre class="font-mono text-xs leading-relaxed whitespace-pre-wrap break-all">{{ runLogs.join('\n') }}</pre>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  </div>
</template>
