<script setup lang="ts">
import { ref, computed, watch } from 'vue'
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
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

// ── Types ──────────────────────────────────────────────────────────────────

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

const { hasTenant } = useTenant()

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
}

function selectAdapter(id: string) {
  selectedAdapterId.value = id
}

function nextStep() {
  if (wizardStep.value === 1) {
    if (!selectedAdapterId.value) return
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

// ── Final approval ─────────────────────────────────────────────────────────

function approveOntology() {
  // The full data source + ontology pipeline is not yet wired to the backend.
  // The API adapters will be available in the Ingestion bounded context.
  toast.info('Data source connection coming soon', {
    description:
      'Your configuration and ontology have been reviewed. The full ingestion pipeline will be available in an upcoming release.',
    duration: 8000,
  })
  wizardOpen.value = false
}

// ── Sync monitoring state ──────────────────────────────────────────────────

// No data sources exist yet (backend not implemented).
// The list is intentionally empty to reflect real system state.
const dataSources = ref<never[]>([])
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
        <!-- Future: data source cards with sync status, history, trigger -->
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
            <Button :disabled="!ontologyReady" @click="approveOntology">
              <CheckCircle2 class="mr-2 size-4" />
              Approve &amp; Start Extraction
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
