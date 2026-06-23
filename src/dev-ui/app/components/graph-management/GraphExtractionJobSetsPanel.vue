<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { Loader2, Save, Layers, FolderSearch, Network, Sparkles, Pencil } from 'lucide-vue-next'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const props = withDefaults(
  defineProps<{
    kgId: string
    reloadNonce?: number
    embedded?: boolean
  }>(),
  { reloadNonce: 0, embedded: true },
)

const emit = defineEmits<{
  saved: []
}>()

const { apiFetch } = useApiClient()

const inputClass =
  'flex h-10 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40'

interface ExtractionJobSet {
  name: string
  enabled?: boolean
  description?: string
  strategy: 'by_instances' | 'by_files'
  entity_type?: string
  instances_per_job?: number
  file_patterns?: string[]
  files_per_job?: number
}

interface EntityTypeOption {
  name: string
  instance_count: number
}

interface ExtractionJobsDocument {
  version: string
  job_sets: ExtractionJobSet[]
}

interface ExtractionJobsGetResponse extends ExtractionJobsDocument {
  entity_types?: EntityTypeOption[]
}

const loading = ref(true)
const saving = ref(false)
const doc = ref<ExtractionJobsDocument | null>(null)
const entityTypeOptions = ref<EntityTypeOption[]>([])
const descriptionEditorOpen = ref(false)
const descriptionEditorIndex = ref<number | null>(null)

const descriptionEditorJobSet = computed(() => {
  if (!doc.value || descriptionEditorIndex.value === null) return null
  return doc.value.job_sets[descriptionEditorIndex.value] ?? null
})

function openDescriptionEditor(index: number) {
  descriptionEditorIndex.value = index
  descriptionEditorOpen.value = true
}

function closeDescriptionEditor() {
  descriptionEditorOpen.value = false
  descriptionEditorIndex.value = null
}

function cloneDoc(d: ExtractionJobsDocument): ExtractionJobsDocument {
  return JSON.parse(JSON.stringify(d)) as ExtractionJobsDocument
}

async function load() {
  loading.value = true
  try {
    const data = await apiFetch<ExtractionJobsGetResponse>(
      `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/extraction-jobs`,
    )
    entityTypeOptions.value = Array.isArray(data.entity_types)
      ? [...data.entity_types].sort((a, b) => a.name.localeCompare(b.name))
      : []
    doc.value = cloneDoc({
      version: data.version || '1.0',
      job_sets: Array.isArray(data.job_sets)
        ? data.job_sets.map((js) => ({ enabled: js.enabled !== false, ...js }))
        : [],
    })
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    toast.error('Failed to load extraction jobs', { description: msg })
    doc.value = { version: '1.0', job_sets: [] }
  } finally {
    loading.value = false
  }
}

function onStrategyChange(js: ExtractionJobSet, strategy: 'by_instances' | 'by_files') {
  if (js.strategy === strategy) return
  js.strategy = strategy
  if (strategy === 'by_instances') {
    delete js.file_patterns
    delete js.files_per_job
    if (!js.entity_type?.trim()) js.entity_type = entityTypeOptions.value[0]?.name ?? ''
    if (js.instances_per_job === undefined) js.instances_per_job = 4
  } else {
    delete js.entity_type
    delete js.instances_per_job
    if (!js.file_patterns?.length) js.file_patterns = ['**/*']
    if (js.files_per_job === undefined) js.files_per_job = 10
  }
}

function addJobSet() {
  if (!doc.value) return
  const index = doc.value.job_sets.length + 1
  doc.value.job_sets.push({
    name: `job_set_${index}`,
    enabled: true,
    strategy: 'by_instances',
    entity_type: entityTypeOptions.value[0]?.name ?? '',
    instances_per_job: 4,
    description: '',
  })
}

function buildPayload(): ExtractionJobsDocument {
  if (!doc.value) throw new Error('No document loaded')
  return {
    version: doc.value.version || '1.0',
    job_sets: doc.value.job_sets.map((js) => {
      const base = {
        name: js.name,
        strategy: js.strategy,
        enabled: js.enabled !== false,
      } as ExtractionJobSet
      if (typeof js.description === 'string' && js.description.trim()) {
        base.description = js.description.trim()
      }
      if (js.strategy === 'by_instances') {
        base.entity_type = js.entity_type ?? ''
        const n = Number(js.instances_per_job)
        if (Number.isFinite(n) && n >= 1) base.instances_per_job = Math.floor(n)
        return base
      }
      base.file_patterns = Array.isArray(js.file_patterns) ? [...js.file_patterns] : []
      const f = Number(js.files_per_job)
      if (Number.isFinite(f) && f >= 1) base.files_per_job = Math.floor(f)
      return base
    }),
  }
}

function getEntityTypeInstanceCount(entityType?: string): number | null {
  if (!entityType?.trim()) return null
  const hit = entityTypeOptions.value.find((x) => x.name === entityType)
  return hit ? hit.instance_count : null
}

function jobSetErrors(js: ExtractionJobSet): string[] {
  if (js.enabled === false) return []
  const errs: string[] = []
  if (js.strategy === 'by_instances') {
    if (!js.entity_type?.trim()) errs.push('Entity type is required for by_instances.')
    if (getEntityTypeInstanceCount(js.entity_type) === 0) {
      errs.push('Selected entity type has 0 instances.')
    }
    const n = Number(js.instances_per_job)
    if (!Number.isInteger(n) || n < 1) errs.push('instances_per_job must be an integer greater than 0.')
    if (!js.description?.trim()) errs.push('Per-instance extraction description is required.')
  }
  return errs
}

function projectedJobCount(js: ExtractionJobSet): number | null {
  if (js.enabled === false) return 0
  if (js.strategy !== 'by_instances') return null
  const total = getEntityTypeInstanceCount(js.entity_type)
  const perJob = Number(js.instances_per_job)
  if (total === null || !Number.isInteger(perJob) || perJob < 1) return null
  if (total <= 0) return 0
  return Math.ceil(total / perJob)
}

const hasValidationErrors = computed(() => {
  if (!doc.value) return false
  return doc.value.job_sets.some((js) => jobSetErrors(js).length > 0)
})

async function save() {
  if (!doc.value) return
  saving.value = true
  try {
    const res = await apiFetch<{ message?: string; warnings?: string[] }>(
      `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/extraction-jobs`,
      { method: 'PUT', body: buildPayload() },
    )
    toast.success('Saved job sets', {
      description: res.message || 'Pending jobs were synced for enabled job sets.',
    })
    if (Array.isArray(res.warnings) && res.warnings.length > 0) {
      toast.warning('Some job sets were not refreshed', {
        description: res.warnings.join(' '),
      })
    }
    emit('saved')
    await load()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    toast.error('Save failed', { description: msg })
  } finally {
    saving.value = false
  }
}

watch(
  () => [props.kgId, props.reloadNonce] as const,
  () => { void load() },
  { immediate: true },
)

defineExpose({ refresh: load })
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-start gap-3 border-b pb-3">
      <div class="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary font-bold text-primary-foreground">
        <Layers class="size-4" />
      </div>
      <div>
        <h2 class="text-lg font-semibold tracking-tight">Extraction Job — Job Sets</h2>
        <p class="text-xs text-muted-foreground">
          Define how extraction work is batched. Each job set runs to completion before the next begins.
          Use per-instance descriptions to guide extraction agents (no separate extraction plan document).
        </p>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-12">
      <Loader2 class="size-8 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="doc">
      <Card>
        <CardHeader>
          <CardTitle class="flex items-center gap-2 text-base">
            <Sparkles class="size-4 text-primary" />
            Job sets
          </CardTitle>
          <CardDescription>
            Author with the assistant above or edit directly. Save syncs pending jobs for enabled sets only — you can add or enable sets while extraction is running.
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-6">
          <div v-if="doc.job_sets.length === 0" class="text-sm text-muted-foreground">
            No job sets yet. Add one below or ask the assistant to define extraction batches.
          </div>

          <div
            v-for="(js, idx) in doc.job_sets"
            :key="`${js.name}-${idx}`"
            class="space-y-4 rounded-xl border border-cyan-500/30 bg-gradient-to-br from-cyan-500/10 via-card to-card p-4 md:p-5"
            :class="js.enabled === false ? 'opacity-60' : ''"
          >
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="space-y-1">
                <input v-model="js.name" :class="inputClass" placeholder="Job set name" />
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <label class="flex items-center gap-2 text-xs text-muted-foreground">
                  <input v-model="js.enabled" type="checkbox" class="size-4 rounded border-border" />
                  Enabled
                </label>
                <Badge variant="outline" class="text-[11px]">#{{ idx + 1 }}</Badge>
              </div>
            </div>

            <div class="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                class="flex items-start gap-2 rounded-lg border px-3 py-2 text-left text-sm"
                :class="js.strategy === 'by_instances' ? 'border-primary/40 bg-primary/15' : 'border-border'"
                @click="onStrategyChange(js, 'by_instances')"
              >
                <Network class="mt-0.5 size-4 shrink-0 text-cyan-500" />
                <span>
                  <span class="block font-medium">By instances</span>
                  <span class="block text-[11px] text-muted-foreground">Enrich known entities</span>
                </span>
              </button>
              <button
                type="button"
                class="flex items-start gap-2 rounded-lg border px-3 py-2 text-left text-sm"
                :class="js.strategy === 'by_files' ? 'border-primary/40 bg-primary/15' : 'border-border'"
                @click="onStrategyChange(js, 'by_files')"
              >
                <FolderSearch class="mt-0.5 size-4 shrink-0 text-violet-500" />
                <span>
                  <span class="block font-medium">By files</span>
                  <span class="block text-[11px] text-muted-foreground">Discover from file patterns</span>
                </span>
              </button>
            </div>

            <template v-if="js.strategy === 'by_instances'">
              <div class="space-y-1.5">
                <label class="text-xs font-medium">Entity type</label>
                <select v-model="js.entity_type" :class="inputClass">
                  <option value="" disabled>Select entity type</option>
                  <option v-for="opt in entityTypeOptions" :key="opt.name" :value="opt.name">
                    {{ opt.name }} ({{ opt.instance_count }} instances)
                  </option>
                </select>
              </div>
              <div class="grid gap-3 sm:grid-cols-2">
                <div class="space-y-1.5">
                  <label class="text-xs font-medium">Instances per job</label>
                  <input v-model.number="js.instances_per_job" type="number" min="1" :class="inputClass" />
                </div>
                <div class="space-y-1.5">
                  <label class="text-xs font-medium">Projected jobs</label>
                  <div class="flex h-10 items-center rounded-lg border border-dashed bg-muted/30 px-3 font-mono text-sm">
                    {{ projectedJobCount(js) ?? '—' }}
                  </div>
                </div>
              </div>
            </template>

            <div class="space-y-1.5">
              <div class="flex items-center justify-between gap-2">
                <label class="text-xs font-medium">Per-instance extraction description</label>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  class="h-7 shrink-0 px-2 text-xs"
                  @click="openDescriptionEditor(idx)"
                >
                  <Pencil class="mr-1 size-3" />
                  Edit
                </Button>
              </div>
              <textarea
                v-model="js.description"
                rows="3"
                class="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                placeholder="Describe what to extract for each instance in this job set."
              />
            </div>

            <ul v-if="jobSetErrors(js).length" class="list-disc space-y-1 pl-4 text-xs text-destructive">
              <li v-for="(err, ei) in jobSetErrors(js)" :key="`${idx}-err-${ei}`">{{ err }}</li>
            </ul>
          </div>
        </CardContent>
        <CardFooter class="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" @click="addJobSet">Add job set</Button>
          <Button size="sm" :disabled="saving || hasValidationErrors" @click="save">
            <Loader2 v-if="saving" class="mr-1.5 size-3.5 animate-spin" />
            <Save v-else class="mr-1.5 size-3.5" />
            Save job sets
          </Button>
        </CardFooter>
      </Card>
    </template>

    <Dialog :open="descriptionEditorOpen" @update:open="(open) => { if (!open) closeDescriptionEditor() }">
      <DialogContent class="flex max-h-[90dvh] flex-col gap-0 overflow-hidden sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Edit per-instance description</DialogTitle>
          <DialogDescription v-if="descriptionEditorJobSet">
            Job set: {{ descriptionEditorJobSet.name }}
          </DialogDescription>
        </DialogHeader>
        <div class="min-h-0 flex-1 overflow-y-auto py-4">
          <textarea
            v-if="descriptionEditorJobSet"
            v-model="descriptionEditorJobSet.description"
            rows="18"
            class="min-h-[min(60dvh,28rem)] w-full resize-y rounded-lg border border-border bg-background px-3 py-2 text-sm leading-relaxed"
            placeholder="Describe what to extract for each instance in this job set."
          />
        </div>
        <DialogFooter>
          <Button type="button" @click="closeDescriptionEditor">Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
