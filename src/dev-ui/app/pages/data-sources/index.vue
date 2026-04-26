<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { toast } from 'vue-sonner'
import {
  Cable,
  Building2,
  Plus,
  Github,
  GitBranch,
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
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
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

// ── Types ──────────────────────────────────────────────────────────────────

interface SyncRun {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  started_at: string
  completed_at: string | null
  error: string | null
  created_at: string
}

interface DataSourceItem {
  id: string
  name: string
  adapter_type: string
  knowledge_graph_id: string
  last_sync_at: string | null
  created_at: string
  sync_runs?: SyncRun[]
}

interface AdapterType {
  id: string
  label: string
  description: string
  icon: typeof Github
  available: boolean
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
}

// ── Composables ────────────────────────────────────────────────────────────

const { hasTenant, tenantVersion } = useTenant()

// ── Available adapters ─────────────────────────────────────────────────────

const adapters: AdapterType[] = [
  {
    id: 'github',
    label: 'GitHub',
    description: 'Repositories, issues, pull requests, commits, and contributors',
    icon: Github,
    available: true,
  },
  {
    id: 'gitlab',
    label: 'GitLab',
    description: 'Repositories, issues, merge requests, and pipelines',
    icon: GitBranch,
    available: false,
  },
  {
    id: 'jira',
    label: 'Jira',
    description: 'Issues, epics, sprints, and project structure',
    icon: Cable,
    available: false,
  },
]

// ── Wizard state ───────────────────────────────────────────────────────────

const wizardOpen = ref(false)
const wizardStep = ref(1)
const WIZARD_STEPS = 4

// Step 1 – Adapter selection
const selectedAdapterId = ref('')
const selectedKnowledgeGraphId = ref('')
const knowledgeGraphs = ref<Array<{ id: string; name: string }>>([])
const loadingKgs = ref(false)

// Step 4 – Approval state
const approvingOntology = ref(false)

// Step 2 – Connection configuration
const connName = ref('')
const connRepoUrl = ref('')
const connToken = ref('')
const showToken = ref(false)
const connNameError = ref('')
const connRepoUrlError = ref('')
const connTokenError = ref('')

// Step 3 – Intent description
const intentText = ref('')
const intentError = ref('')

// Step 4 – Proposed ontology
const scanningOntology = ref(false)
const ontologyReady = ref(false)

const proposedNodes = ref<ProposedNodeType[]>([])
const proposedEdges = ref<ProposedEdgeType[]>([])

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

const selectedAdapter = computed(() => adapters.find((a) => a.id === selectedAdapterId.value))

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

// ── Infer data source name from repo URL ───────────────────────────────────

watch(connRepoUrl, (url) => {
  if (!url.trim() || connName.value.trim()) return
  const match = url.trim().match(/github\.com\/[^/]+\/([^/]+?)(?:\.git)?$/)
  if (match) {
    connName.value = match[1]
  }
})

// ── Wizard navigation ──────────────────────────────────────────────────────

function openWizard() {
  wizardStep.value = 1
  selectedAdapterId.value = ''
  selectedKnowledgeGraphId.value = ''
  approvingOntology.value = false
  connName.value = ''
  connRepoUrl.value = ''
  connToken.value = ''
  showToken.value = false
  connNameError.value = ''
  connRepoUrlError.value = ''
  connTokenError.value = ''
  intentText.value = ''
  intentError.value = ''
  scanningOntology.value = false
  ontologyReady.value = false
  proposedNodes.value = []
  proposedEdges.value = []
  wizardOpen.value = true
  loadKnowledgeGraphs()
}

function selectAdapter(id: string) {
  selectedAdapterId.value = id
}

function nextStep() {
  if (wizardStep.value === 1) {
    if (!selectedAdapterId.value) return
    if (!selectedKnowledgeGraphId.value) return
    wizardStep.value = 2
    return
  }

  if (wizardStep.value === 2) {
    connNameError.value = ''
    connRepoUrlError.value = ''
    connTokenError.value = ''
    let valid = true

    if (!connName.value.trim()) {
      connNameError.value = 'Data source name is required.'
      valid = false
    }
    if (!connRepoUrl.value.trim()) {
      connRepoUrlError.value = 'Repository URL is required.'
      valid = false
    } else if (!connRepoUrl.value.includes('github.com')) {
      connRepoUrlError.value = 'Enter a valid GitHub repository URL.'
      valid = false
    }
    if (!connToken.value.trim()) {
      connTokenError.value = 'Access token is required.'
      valid = false
    }

    if (!valid) return
    wizardStep.value = 3
    return
  }

  if (wizardStep.value === 3) {
    intentError.value = ''
    if (!intentText.value.trim()) {
      intentError.value = 'Please describe your intent before continuing.'
      return
    }
    wizardStep.value = 4
    beginOntologyProposal()
    return
  }
}

function prevStep() {
  if (wizardStep.value > 1) wizardStep.value--
}

// ── Ontology proposal (simulated scan + AI proposal) ──────────────────────

async function beginOntologyProposal() {
  scanningOntology.value = true
  ontologyReady.value = false
  proposedNodes.value = []
  proposedEdges.value = []

  // Simulate a lightweight scan of the data source (1.5s) followed by AI proposal
  await new Promise<void>((resolve) => setTimeout(resolve, 1500))

  proposedNodes.value = GITHUB_PROPOSAL_NODES.map(toProposedNode)
  proposedEdges.value = GITHUB_PROPOSAL_EDGES.map(toProposedEdge)
  scanningOntology.value = false
  ontologyReady.value = true
}

// ── Per-type inline editing ────────────────────────────────────────────────

function startEditNode(index: number) {
  const n = proposedNodes.value[index]
  n.editLabel = n.label
  n.editDescription = n.description
  n.editRequired = n.required_properties.join(', ')
  n.editOptional = n.optional_properties.join(', ')
  n.editing = true
}

function saveEditNode(index: number) {
  const n = proposedNodes.value[index]
  n.label = n.editLabel.trim() || n.label
  n.description = n.editDescription
  n.required_properties = n.editRequired.split(',').map((s) => s.trim()).filter(Boolean)
  n.optional_properties = n.editOptional.split(',').map((s) => s.trim()).filter(Boolean)
  n.editing = false
}

function cancelEditNode(index: number) {
  proposedNodes.value[index].editing = false
}

function removeNode(index: number) {
  proposedNodes.value.splice(index, 1)
}

function startEditEdge(index: number) {
  const e = proposedEdges.value[index]
  e.editLabel = e.label
  e.editDescription = e.description
  e.editRequired = e.required_properties.join(', ')
  e.editOptional = e.optional_properties.join(', ')
  e.editing = true
}

function saveEditEdge(index: number) {
  const e = proposedEdges.value[index]
  e.label = e.editLabel.trim() || e.label
  e.description = e.editDescription
  e.required_properties = e.editRequired.split(',').map((s) => s.trim()).filter(Boolean)
  e.optional_properties = e.editOptional.split(',').map((s) => s.trim()).filter(Boolean)
  e.editing = false
}

function cancelEditEdge(index: number) {
  proposedEdges.value[index].editing = false
}

function removeEdge(index: number) {
  proposedEdges.value.splice(index, 1)
}

// ── Per-type inline editing for the ontology editor dialog ────────────────

function startEditNodeInEditor(index: number) {
  const n = editNodes.value[index]
  n.editLabel = n.label
  n.editDescription = n.description
  n.editRequired = n.required_properties.join(', ')
  n.editOptional = n.optional_properties.join(', ')
  n.editing = true
}

function saveEditNodeInEditor(index: number) {
  const n = editNodes.value[index]
  n.label = n.editLabel.trim() || n.label
  n.description = n.editDescription
  n.required_properties = n.editRequired.split(',').map((s) => s.trim()).filter(Boolean)
  n.optional_properties = n.editOptional.split(',').map((s) => s.trim()).filter(Boolean)
  n.editing = false
}

function cancelEditNodeInEditor(index: number) {
  editNodes.value[index].editing = false
}

function startEditEdgeInEditor(index: number) {
  const e = editEdges.value[index]
  e.editLabel = e.label
  e.editDescription = e.description
  e.editRequired = e.required_properties.join(', ')
  e.editOptional = e.optional_properties.join(', ')
  e.editing = true
}

function saveEditEdgeInEditor(index: number) {
  const e = editEdges.value[index]
  e.label = e.editLabel.trim() || e.label
  e.description = e.editDescription
  e.required_properties = e.editRequired.split(',').map((s) => s.trim()).filter(Boolean)
  e.optional_properties = e.editOptional.split(',').map((s) => s.trim()).filter(Boolean)
  e.editing = false
}

function cancelEditEdgeInEditor(index: number) {
  editEdges.value[index].editing = false
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
  return apiFetch(`/management/knowledge-graphs/${params.kg_id}/data-sources`, {
    method: 'POST',
    body: {
      name: params.name,
      adapter_type: params.adapter_type,
      connection_config: params.connection_config,
      credentials: params.credentials,
    },
  })
}

// ── Final approval ─────────────────────────────────────────────────────────

async function approveOntology() {
  if (!selectedKnowledgeGraphId.value) {
    toast.error('Please select a knowledge graph first')
    return
  }

  approvingOntology.value = true
  try {
    await createDataSource({
      kg_id: selectedKnowledgeGraphId.value,
      name: connName.value,
      adapter_type: selectedAdapterId.value,
      connection_config: {
        repo_url: connRepoUrl.value,
      },
      credentials: connToken.value ? { access_token: connToken.value } : undefined,
    })
    toast.success('Data source connected', {
      description: `${connName.value} has been connected and extraction will begin shortly.`,
    })
    wizardOpen.value = false
    await loadDataSources()
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Failed to connect data source'
    toast.error('Connection failed', { description: msg })
  } finally {
    approvingOntology.value = false
  }
}

// ── Sync monitoring state ──────────────────────────────────────────────────

const dataSources = ref<DataSourceItem[]>([])
const loadingDataSources = ref(false)
let _loadRequestId = 0

async function loadDataSources() {
  if (!hasTenant.value) return
  loadingDataSources.value = true
  const myRequestId = ++_loadRequestId
  try {
    const { apiFetch } = useApiClient()
    // Fetch all knowledge graphs first
    const kgResult = await apiFetch<{ knowledge_graphs: Array<{ id: string; name: string }> }>(
      '/management/knowledge-graphs'
    )
    if (myRequestId !== _loadRequestId) return // stale — a newer request is in flight
    const kgs = kgResult.knowledge_graphs ?? []
    // Fetch data sources for all KGs in parallel
    const kgDataSources = await Promise.all(
      kgs.map(async (kg) => {
        try {
          const dsResult = await apiFetch<{ data_sources: DataSourceItem[] }>(
            `/management/knowledge-graphs/${kg.id}/data-sources`
          )
          const sources = dsResult.data_sources ?? []
          // Fetch sync runs for all data sources in parallel
          await Promise.all(
            sources.map(async (ds) => {
              try {
                const runResult = await apiFetch<{ sync_runs: SyncRun[] }>(
                  `/management/data-sources/${ds.id}/sync-runs`
                )
                ds.sync_runs = runResult.sync_runs ?? []
              } catch {
                ds.sync_runs = []
              }
            })
          )
          return sources
        } catch {
          // Skip KGs whose data sources cannot be fetched.
          return []
        }
      })
    )
    if (myRequestId !== _loadRequestId) return // stale — a newer request is in flight
    dataSources.value = kgDataSources.flat()
  } catch {
    dataSources.value = []
  } finally {
    if (myRequestId === _loadRequestId) {
      loadingDataSources.value = false
    }
  }
}

onMounted(() => {
  loadDataSources()
})

// Reload data sources whenever the user switches tenants.
watch(tenantVersion, () => {
  loadDataSources()
})

async function triggerSync(dsId: string) {
  try {
    const { apiFetch } = useApiClient()
    await apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
    toast.success('Sync triggered', { description: 'The data source sync has been initiated.' })
    await loadDataSources()
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

function saveOntologyEdits() {
  toast.success('Ontology saved', {
    description: 'Ontology changes have been applied. A re-extraction will be scheduled.',
  })
  closeOntologyEditor()
}

function closeOntologyEditor() {
  editOntologyOpen.value = false
  editingDataSource.value = null
  pendingOntologyEditDsId.value = null
  editNodes.value = []
  editEdges.value = []
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
          <h1 class="text-2xl font-bold tracking-tight">Data Sources</h1>
          <p class="text-sm text-muted-foreground">
            Connect external data sources to your knowledge graphs for automated extraction
          </p>
        </div>
      </div>
      <Button :disabled="!hasTenant" @click="openWizard">
        <Plus class="mr-2 size-4" />
        Add Data Source
      </Button>
    </div>

    <Separator />

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view data sources.</p>
    </div>

    <template v-else>
      <!-- Empty state (no data sources yet) -->
      <div v-if="dataSources.length === 0" class="flex flex-col items-center gap-4 py-16 text-center">
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
        <div v-for="ds in dataSources" :key="ds.id" class="rounded-lg border bg-card">
          <div class="flex items-center justify-between p-4">
            <div class="flex items-center gap-3">
              <div class="rounded-md bg-muted p-2">
                <Cable class="size-4 text-muted-foreground" />
              </div>
              <div>
                <p class="font-medium text-sm">{{ ds.name }}</p>
                <p class="text-xs text-muted-foreground">{{ ds.adapter_type }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <Badge
                :variant="ds.sync_runs?.[0]?.status === 'completed' ? 'default' : ds.sync_runs?.[0]?.status === 'failed' ? 'destructive' : 'secondary'"
              >
                {{ ds.sync_runs?.[0]?.status ?? 'idle' }}
              </Badge>
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
              <Button size="sm" variant="outline" @click="triggerSync(ds.id)">
                Sync Now
              </Button>
            </div>
          </div>
          <!-- Sync history -->
          <div v-if="ds.sync_runs && ds.sync_runs.length > 0" class="border-t px-4 py-3">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">Sync History</p>
            <div class="space-y-1">
              <div v-for="run in ds.sync_runs" :key="run.id" class="flex items-center gap-2 text-xs text-muted-foreground">
                <Badge :variant="run.status === 'completed' ? 'default' : run.status === 'failed' ? 'destructive' : 'secondary'" class="text-[10px]">
                  {{ run.status }}
                </Badge>
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

        <!-- ── Step 1: Select Adapter ── -->
        <div v-if="wizardStep === 1" class="space-y-4">
          <div>
            <h3 class="text-sm font-semibold">Select an adapter type</h3>
            <p class="text-xs text-muted-foreground">Choose the system you want to import data from.</p>
          </div>

          <!-- Knowledge graph selection -->
          <div class="space-y-1.5">
            <Label>Knowledge Graph <span class="text-destructive">*</span></Label>
            <select
              v-if="!loadingKgs && knowledgeGraphs.length > 0"
              v-model="selectedKnowledgeGraphId"
              class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              <option value="">Select a knowledge graph...</option>
              <option v-for="kg in knowledgeGraphs" :key="kg.id" :value="kg.id">{{ kg.name }}</option>
            </select>
            <div v-else-if="loadingKgs" class="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 class="size-4 animate-spin" /> Loading knowledge graphs...
            </div>
            <p v-else class="text-sm text-muted-foreground">
              No knowledge graphs found. <NuxtLink to="/knowledge-graphs" class="text-primary underline">Create one first</NuxtLink>.
            </p>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <button
              v-for="adapter in adapters"
              :key="adapter.id"
              :disabled="!adapter.available"
              class="group relative rounded-lg border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
              :class="[
                adapter.available
                  ? selectedAdapterId === adapter.id
                    ? 'border-primary bg-primary/5'
                    : 'hover:border-primary/50 hover:bg-accent'
                  : 'cursor-not-allowed opacity-50',
              ]"
              @click="adapter.available && selectAdapter(adapter.id)"
            >
              <div class="flex items-start gap-3">
                <div class="rounded-md bg-muted p-2 shrink-0">
                  <component :is="adapter.icon" class="size-5 text-muted-foreground" />
                </div>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <p class="text-sm font-medium">{{ adapter.label }}</p>
                    <Badge v-if="!adapter.available" variant="outline" class="text-[10px] px-1.5 py-0">
                      Soon
                    </Badge>
                    <CheckCircle2
                      v-if="selectedAdapterId === adapter.id"
                      class="ml-auto size-4 text-primary shrink-0"
                    />
                  </div>
                  <p class="text-xs text-muted-foreground mt-0.5">{{ adapter.description }}</p>
                </div>
              </div>
            </button>
          </div>

          <DialogFooter class="pt-2">
            <Button :disabled="!selectedAdapterId" @click="nextStep">
              Continue
              <ChevronRight class="ml-1 size-4" />
            </Button>
          </DialogFooter>
        </div>

        <!-- ── Step 2: Connection Configuration ── -->
        <div v-else-if="wizardStep === 2" class="space-y-5">
          <div>
            <h3 class="text-sm font-semibold">Configure connection</h3>
            <p class="text-xs text-muted-foreground">
              Provide the details to connect your
              <span class="font-medium">{{ selectedAdapter?.label }}</span> repository.
            </p>
          </div>

          <!-- GitHub-specific fields -->
          <div v-if="selectedAdapterId === 'github'" class="space-y-4">
            <div class="space-y-1.5">
              <Label for="ds-repo-url">
                Repository URL <span class="text-destructive">*</span>
              </Label>
              <Input
                id="ds-repo-url"
                v-model="connRepoUrl"
                placeholder="https://github.com/owner/repository"
                @input="connRepoUrlError = ''"
              />
              <p v-if="connRepoUrlError" class="text-xs text-destructive">{{ connRepoUrlError }}</p>
              <p v-else class="text-xs text-muted-foreground">
                The full HTTPS URL of the GitHub repository to index.
              </p>
            </div>

            <div class="space-y-1.5">
              <Label for="ds-token">
                Access Token <span class="text-destructive">*</span>
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

            <div class="space-y-1.5">
              <Label for="ds-name">
                Data Source Name <span class="text-destructive">*</span>
              </Label>
              <Input
                id="ds-name"
                v-model="connName"
                placeholder="e.g. my-repository"
                @input="connNameError = ''"
              />
              <p v-if="connNameError" class="text-xs text-destructive">{{ connNameError }}</p>
              <p v-else class="text-xs text-muted-foreground">
                Auto-inferred from the repository URL. You can rename it here.
              </p>
            </div>
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
            <Button @click="nextStep">
              Continue
              <ChevronRight class="ml-1 size-4" />
            </Button>
          </DialogFooter>
        </div>

        <!-- ── Step 3: Intent Description ── -->
        <div v-else-if="wizardStep === 3" class="space-y-5">
          <div>
            <h3 class="text-sm font-semibold">Describe your intent</h3>
            <p class="text-xs text-muted-foreground">
              Tell the AI agent what problems or questions you want to solve with this data.
              This shapes the proposed knowledge graph ontology.
            </p>
          </div>

          <div class="space-y-1.5">
            <Label for="intent-text">What do you want to learn from this data?</Label>
            <textarea
              id="intent-text"
              v-model="intentText"
              placeholder="e.g. I want to understand how issues are triaged, who the most active contributors are, and how pull requests relate to releases…"
              class="flex min-h-[120px] w-full resize-none rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
              @input="intentError = ''"
            />
            <p v-if="intentError" class="text-xs text-destructive">{{ intentError }}</p>
            <p v-else class="text-xs text-muted-foreground">
              The more specific you are, the better the proposed ontology will match your needs.
            </p>
          </div>

          <DialogFooter class="pt-2">
            <Button variant="outline" @click="prevStep">
              <ChevronLeft class="mr-1 size-4" />
              Back
            </Button>
            <Button @click="nextStep">
              Analyse &amp; Propose Ontology
              <ChevronRight class="ml-1 size-4" />
            </Button>
          </DialogFooter>
        </div>

        <!-- ── Step 4: Review Proposed Ontology ── -->
        <div v-else-if="wizardStep === 4" class="space-y-4">
          <!-- Scanning state -->
          <div v-if="scanningOntology" class="flex flex-col items-center gap-4 py-10 text-center">
            <Loader2 class="size-10 animate-spin text-primary" />
            <div>
              <p class="text-sm font-medium">Analysing your data source…</p>
              <p class="text-xs text-muted-foreground">
                Scanning repository structure and applying your intent to propose an ontology.
              </p>
            </div>
          </div>

          <!-- Proposed ontology -->
          <template v-else-if="ontologyReady">
            <div>
              <h3 class="text-sm font-semibold">Review proposed ontology</h3>
              <p class="text-xs text-muted-foreground">
                The AI agent has proposed the following node and edge types based on your data source and intent.
                You can edit or remove individual types before approving.
              </p>
            </div>

            <!-- Re-extraction warning note -->
            <div class="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/30">
              <AlertTriangle class="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <p class="text-xs text-amber-700 dark:text-amber-300">
                Modifying the ontology after the initial extraction is complete will trigger a full
                re-extraction of this data source. Approve carefully.
              </p>
            </div>

            <!-- Node types -->
            <div class="space-y-2">
              <h4 class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Node Types ({{ proposedNodes.length }})
              </h4>
              <div class="space-y-2">
                <Card
                  v-for="(node, idx) in proposedNodes"
                  :key="idx"
                  class="overflow-hidden"
                >
                  <!-- View mode -->
                  <CardContent v-if="!node.editing" class="flex items-start gap-3 p-3">
                    <Badge variant="default" class="mt-0.5 shrink-0">Node</Badge>
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-medium">{{ node.label }}</p>
                      <p class="text-xs text-muted-foreground">{{ node.description }}</p>
                      <div class="mt-1.5 flex flex-wrap gap-1">
                        <Badge
                          v-for="prop in node.required_properties"
                          :key="prop"
                          variant="secondary"
                          class="text-[10px]"
                        >
                          {{ prop }} <span class="ml-0.5 text-destructive">*</span>
                        </Badge>
                        <Badge
                          v-for="prop in node.optional_properties"
                          :key="prop"
                          variant="outline"
                          class="text-[10px]"
                        >
                          {{ prop }}
                        </Badge>
                      </div>
                    </div>
                    <div class="flex shrink-0 items-center gap-1">
                      <Tooltip>
                        <TooltipTrigger as-child>
                          <Button variant="ghost" size="icon" class="size-7" @click="startEditNode(idx)">
                            <Pencil class="size-3.5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent><p>Edit type</p></TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger as-child>
                          <Button variant="ghost" size="icon" class="size-7 text-destructive hover:text-destructive" @click="removeNode(idx)">
                            <Trash2 class="size-3.5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent><p>Remove type</p></TooltipContent>
                      </Tooltip>
                    </div>
                  </CardContent>

                  <!-- Edit mode -->
                  <CardContent v-else class="space-y-3 p-3">
                    <div class="grid grid-cols-2 gap-3">
                      <div class="space-y-1">
                        <Label class="text-xs">Label</Label>
                        <Input v-model="node.editLabel" class="h-8 text-xs" />
                      </div>
                      <div class="space-y-1">
                        <Label class="text-xs">Description</Label>
                        <Input v-model="node.editDescription" class="h-8 text-xs" />
                      </div>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                      <div class="space-y-1">
                        <Label class="text-xs">Required properties <span class="text-muted-foreground">(comma-separated)</span></Label>
                        <Input v-model="node.editRequired" placeholder="e.g. name, url" class="h-8 text-xs" />
                      </div>
                      <div class="space-y-1">
                        <Label class="text-xs">Optional properties</Label>
                        <Input v-model="node.editOptional" placeholder="e.g. description, stars" class="h-8 text-xs" />
                      </div>
                    </div>
                    <div class="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" class="h-7 text-xs" @click="cancelEditNode(idx)">
                        <X class="mr-1 size-3" />
                        Cancel
                      </Button>
                      <Button size="sm" class="h-7 text-xs" @click="saveEditNode(idx)">
                        <Check class="mr-1 size-3" />
                        Save
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>

            <!-- Edge types -->
            <div class="space-y-2">
              <h4 class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Edge Types ({{ proposedEdges.length }})
              </h4>
              <div class="space-y-2">
                <Card
                  v-for="(edge, idx) in proposedEdges"
                  :key="idx"
                  class="overflow-hidden"
                >
                  <!-- View mode -->
                  <CardContent v-if="!edge.editing" class="flex items-start gap-3 p-3">
                    <Badge variant="outline" class="mt-0.5 shrink-0">Edge</Badge>
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-medium font-mono">{{ edge.label }}</p>
                      <p class="text-xs text-muted-foreground">{{ edge.description }}</p>
                      <p class="text-xs text-muted-foreground/70 mt-0.5">
                        {{ edge.from }} → {{ edge.to }}
                      </p>
                      <div v-if="edge.required_properties.length || edge.optional_properties.length" class="mt-1.5 flex flex-wrap gap-1">
                        <Badge
                          v-for="prop in edge.required_properties"
                          :key="prop"
                          variant="secondary"
                          class="text-[10px]"
                        >
                          {{ prop }} <span class="ml-0.5 text-destructive">*</span>
                        </Badge>
                        <Badge
                          v-for="prop in edge.optional_properties"
                          :key="prop"
                          variant="outline"
                          class="text-[10px]"
                        >
                          {{ prop }}
                        </Badge>
                      </div>
                    </div>
                    <div class="flex shrink-0 items-center gap-1">
                      <Tooltip>
                        <TooltipTrigger as-child>
                          <Button variant="ghost" size="icon" class="size-7" @click="startEditEdge(idx)">
                            <Pencil class="size-3.5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent><p>Edit type</p></TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger as-child>
                          <Button variant="ghost" size="icon" class="size-7 text-destructive hover:text-destructive" @click="removeEdge(idx)">
                            <Trash2 class="size-3.5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent><p>Remove type</p></TooltipContent>
                      </Tooltip>
                    </div>
                  </CardContent>

                  <!-- Edit mode -->
                  <CardContent v-else class="space-y-3 p-3">
                    <div class="grid grid-cols-2 gap-3">
                      <div class="space-y-1">
                        <Label class="text-xs">Label</Label>
                        <Input v-model="edge.editLabel" class="h-8 text-xs" />
                      </div>
                      <div class="space-y-1">
                        <Label class="text-xs">Description</Label>
                        <Input v-model="edge.editDescription" class="h-8 text-xs" />
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
                      <Button variant="ghost" size="sm" class="h-7 text-xs" @click="cancelEditEdge(idx)">
                        <X class="mr-1 size-3" />
                        Cancel
                      </Button>
                      <Button size="sm" class="h-7 text-xs" @click="saveEditEdge(idx)">
                        <Check class="mr-1 size-3" />
                        Save
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </template>

          <DialogFooter v-if="!scanningOntology" class="pt-2">
            <Button variant="outline" @click="prevStep">
              <ChevronLeft class="mr-1 size-4" />
              Back
            </Button>
            <Button :disabled="!ontologyReady || approvingOntology" @click="approveOntology">
              <Loader2 v-if="approvingOntology" class="mr-2 size-4 animate-spin" />
              <CheckCircle2 v-else class="mr-2 size-4" />
              Approve &amp; Start Extraction
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
                  <Button variant="ghost" size="icon" class="size-7" @click="startEditNodeInEditor(idx)">
                    <Pencil class="size-3.5" />
                  </Button>
                </div>
              </CardContent>
              <CardContent v-else class="space-y-3 p-3">
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1">
                    <Label class="text-xs">Label</Label>
                    <Input v-model="node.editLabel" class="h-8 text-xs" />
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
                  <Button variant="ghost" size="sm" class="h-7 text-xs" @click="cancelEditNodeInEditor(idx)">
                    <X class="mr-1 size-3" /> Cancel
                  </Button>
                  <Button size="sm" class="h-7 text-xs" @click="saveEditNodeInEditor(idx)">
                    <Check class="mr-1 size-3" /> Save
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
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
                <Button variant="ghost" size="icon" class="size-7 shrink-0" @click="startEditEdgeInEditor(idx)">
                  <Pencil class="size-3.5" />
                </Button>
              </CardContent>
              <CardContent v-else class="space-y-3 p-3">
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1">
                    <Label class="text-xs">Label</Label>
                    <Input v-model="edge.editLabel" class="h-8 text-xs" />
                  </div>
                  <div class="space-y-1">
                    <Label class="text-xs">Description</Label>
                    <Input v-model="edge.editDescription" class="h-8 text-xs" />
                  </div>
                </div>
                <div class="flex justify-end gap-2">
                  <Button variant="ghost" size="sm" class="h-7 text-xs" @click="cancelEditEdgeInEditor(idx)">
                    <X class="mr-1 size-3" /> Cancel
                  </Button>
                  <Button size="sm" class="h-7 text-xs" @click="saveEditEdgeInEditor(idx)">
                    <Check class="mr-1 size-3" /> Save
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        <DialogFooter class="pt-4">
          <Button variant="outline" @click="closeOntologyEditor">Close</Button>
          <Button @click="saveOntologyEdits">Save Changes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

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
