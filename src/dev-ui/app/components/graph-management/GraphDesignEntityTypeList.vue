<script setup lang="ts">
import { computed, ref, toRef, watch } from 'vue'
import { ChevronDown, Loader2, Search, X } from 'lucide-vue-next'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useDesignArtifactInstanceQuery } from '@/composables/useDesignArtifactInstanceQuery'
import {
  type DesignArtifactEntityType,
  DESIGN_ARTIFACT_INSTANCE_PAGE_SIZE,
  prepopulationBadgeClass,
  prepopulationCardClass,
  prepopulationLabel,
  searchableEntityProperties,
} from '@/utils/kgDesignArtifacts'

const props = defineProps<{
  kgId: string
  rows: DesignArtifactEntityType[]
  reloadNonce?: number
}>()

const kgId = toRef(props, 'kgId')
const reloadNonce = computed(() => props.reloadNonce ?? 0)

const {
  entityStates,
  ensureEntityState,
  searchEntityInstances,
  clearEntitySearch,
  loadMoreEntityInstances,
} = useDesignArtifactInstanceQuery(kgId, reloadNonce)

const draftSearchProperty = ref<Record<string, string>>({})
const draftSearchValue = ref<Record<string, string>>({})

watch(
  () => props.rows,
  (rows) => {
    for (const row of rows) {
      const state = ensureEntityState(row.type, {
        instances: row.instances ?? [],
        total: row.instance_count,
      })
      if (!state.activeSearch) {
        state.instances = [...(row.instances ?? [])]
        state.total = row.instance_count
      }
      if (!draftSearchProperty.value[row.type]) {
        draftSearchProperty.value[row.type] = searchableEntityProperties(row)[0] ?? 'slug'
      }
    }
  },
  { immediate: true, deep: true },
)

function propertyOptions(row: DesignArtifactEntityType): string[] {
  return searchableEntityProperties(row)
}

function canLoadMore(row: DesignArtifactEntityType): boolean {
  const state = ensureEntityState(row.type)
  return state.instances.length < state.total
}

async function runSearch(row: DesignArtifactEntityType) {
  const propertyName = draftSearchProperty.value[row.type]
  const propertyValue = draftSearchValue.value[row.type] ?? ''
  if (!propertyName || !propertyValue.trim()) return
  await searchEntityInstances(row.type, {
    entityType: row.type,
    propertyName,
    propertyValue: propertyValue.trim(),
  })
}

async function resetSearch(row: DesignArtifactEntityType) {
  draftSearchValue.value[row.type] = ''
  await clearEntitySearch(row.type, {
    entityType: row.type,
    seedInstances: row.instances ?? [],
    total: row.instance_count,
  })
}

async function loadMore(row: DesignArtifactEntityType) {
  await loadMoreEntityInstances(row.type, { entityType: row.type })
}

const visibleRows = computed(() => props.rows)
</script>

<template>
  <div class="space-y-1.5">
    <Card
      v-for="row in visibleRows"
      :key="row.type"
      :class="['overflow-hidden', prepopulationCardClass(row.prepopulated_instances)]"
    >
      <details class="group">
        <summary
          class="flex cursor-pointer list-none items-center gap-2 px-2.5 py-2 [&::-webkit-details-marker]:hidden"
        >
          <ChevronDown
            class="size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
          />
          <div class="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
            <span class="text-sm font-semibold leading-tight">{{ row.type }}</span>
            <Badge
              variant="outline"
              class="h-5 px-1.5 text-[10px]"
              :class="prepopulationBadgeClass(row.prepopulated_instances)"
            >
              {{ prepopulationLabel(row.prepopulated_instances) }}
            </Badge>
            <Badge variant="secondary" class="h-5 px-1.5 text-[10px]">
              {{ row.instance_count }} instance{{ row.instance_count === 1 ? '' : 's' }}
            </Badge>
          </div>
        </summary>
        <div class="space-y-2 border-t px-2.5 pb-2.5 pt-0">
          <p v-if="row.description" class="pt-2 text-xs leading-snug text-muted-foreground">
            {{ row.description }}
          </p>
          <div v-else class="pt-1.5 text-xs italic text-muted-foreground">No description</div>

          <div class="space-y-1">
            <p class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Properties
            </p>
            <div
              v-if="row.property_definitions && Object.keys(row.property_definitions).length > 0"
              class="divide-y rounded-md border text-xs"
            >
              <div
                v-for="(label, key) in row.property_definitions"
                :key="key"
                class="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 px-2 py-1"
              >
                <code class="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">{{ key }}</code>
                <span class="text-muted-foreground">{{ label }}</span>
                <Badge
                  v-if="row.required_properties?.includes(String(key))"
                  variant="outline"
                  class="h-4 px-1 text-[9px]"
                >
                  required
                </Badge>
                <Badge
                  v-else-if="row.optional_properties?.includes(String(key))"
                  variant="outline"
                  class="h-4 px-1 text-[9px] opacity-70"
                >
                  optional
                </Badge>
              </div>
            </div>
            <p v-else class="text-xs text-muted-foreground">No property definitions</p>
          </div>

          <details v-if="row.instance_count > 0" class="group/inst rounded-md border">
            <summary
              class="flex cursor-pointer list-none items-center gap-1.5 px-2 py-1.5 text-xs font-medium hover:bg-muted/50 [&::-webkit-details-marker]:hidden"
            >
              <ChevronDown
                class="size-3.5 shrink-0 text-muted-foreground transition-transform group-open/inst:rotate-180"
              />
              Instances
              <span class="font-normal text-muted-foreground">
                (showing {{ ensureEntityState(row.type).instances.length }} of
                {{ ensureEntityState(row.type).total }})
              </span>
            </summary>
            <div class="space-y-2 border-t p-2">
              <div class="flex flex-wrap items-end gap-2" @click.stop>
                <div class="min-w-[8rem] flex-1 space-y-1">
                  <label class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    Property
                  </label>
                  <Select v-model="draftSearchProperty[row.type]">
                    <SelectTrigger class="h-8 text-xs">
                      <SelectValue placeholder="Select property" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem
                        v-for="prop in propertyOptions(row)"
                        :key="prop"
                        :value="prop"
                        class="text-xs"
                      >
                        {{ prop }}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div class="min-w-[10rem] flex-[2] space-y-1">
                  <label class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    Search value
                  </label>
                  <Input
                    v-model="draftSearchValue[row.type]"
                    class="h-8 text-xs"
                    placeholder="Contains…"
                    @keydown.enter.prevent="runSearch(row)"
                  />
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  class="h-8 px-2 text-xs"
                  :disabled="entityStates[row.type]?.loading"
                  @click.stop.prevent="runSearch(row)"
                >
                  <Loader2 v-if="entityStates[row.type]?.loading" class="mr-1 size-3.5 animate-spin" />
                  <Search v-else class="mr-1 size-3.5" />
                  Search
                </Button>
                <Button
                  v-if="entityStates[row.type]?.activeSearch"
                  variant="ghost"
                  size="sm"
                  class="h-8 px-2 text-xs"
                  @click.stop.prevent="resetSearch(row)"
                >
                  <X class="mr-1 size-3.5" />
                  Clear
                </Button>
              </div>

              <ul class="space-y-1 text-xs">
                <li
                  v-for="(inst, idx) in ensureEntityState(row.type).instances"
                  :key="inst.slug ?? idx"
                  class="rounded-md bg-muted/40 px-2 py-1"
                >
                  <div class="mb-0.5 font-mono text-[10px] text-muted-foreground">
                    {{ inst.slug ?? '—' }}
                  </div>
                  <pre class="max-h-24 overflow-y-auto whitespace-pre-wrap break-all text-[10px] leading-snug">{{
                    JSON.stringify(inst.properties ?? {}, null, 2)
                  }}</pre>
                </li>
              </ul>

              <p
                v-if="ensureEntityState(row.type).instances.length === 0"
                class="text-xs text-muted-foreground"
              >
                No instances match the current filter.
              </p>

              <div v-if="canLoadMore(row)" class="flex flex-wrap items-center gap-1.5" @click.stop>
                <Button
                  variant="outline"
                  size="sm"
                  class="h-7 px-2 text-xs"
                  :disabled="entityStates[row.type]?.loading"
                  @click.stop.prevent="loadMore(row)"
                >
                  <Loader2 v-if="entityStates[row.type]?.loading" class="mr-1 size-3.5 animate-spin" />
                  Load next {{ DESIGN_ARTIFACT_INSTANCE_PAGE_SIZE }}
                </Button>
                <span class="text-xs text-muted-foreground">
                  {{ ensureEntityState(row.type).instances.length }} loaded ·
                  {{ ensureEntityState(row.type).total - ensureEntityState(row.type).instances.length }}
                  remaining
                </span>
              </div>
            </div>
          </details>
        </div>
      </details>
    </Card>
  </div>
</template>
