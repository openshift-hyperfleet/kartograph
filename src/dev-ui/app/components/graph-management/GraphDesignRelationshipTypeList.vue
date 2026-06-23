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
  type DesignArtifactRelationshipType,
  DESIGN_ARTIFACT_INSTANCE_PAGE_SIZE,
  prepopulationBadgeClass,
  prepopulationCardClass,
  prepopulationLabel,
  searchableRelationshipProperties,
} from '@/utils/kgDesignArtifacts'

const props = defineProps<{
  kgId: string
  rows: DesignArtifactRelationshipType[]
  reloadNonce?: number
}>()

const kgId = toRef(props, 'kgId')
const reloadNonce = computed(() => props.reloadNonce ?? 0)

const {
  relationshipStates,
  ensureRelationshipState,
  searchRelationshipInstances,
  clearRelationshipSearch,
  loadMoreRelationshipInstances,
} = useDesignArtifactInstanceQuery(kgId, reloadNonce)

const draftSearchProperty = ref<Record<string, string>>({})
const draftSearchValue = ref<Record<string, string>>({})

watch(
  () => props.rows,
  (rows) => {
    for (const row of rows) {
      const state = ensureRelationshipState(row.key, {
        instances: row.instances ?? [],
        total: row.instance_count,
      })
      if (!state.activeSearch) {
        state.instances = [...(row.instances ?? [])]
        state.total = row.instance_count
      }
      if (!draftSearchProperty.value[row.key]) {
        draftSearchProperty.value[row.key] = searchableRelationshipProperties(row)[0] ?? 'data_source_id'
      }
    }
  },
  { immediate: true, deep: true },
)

function canLoadMore(row: DesignArtifactRelationshipType): boolean {
  const state = ensureRelationshipState(row.key)
  return state.instances.length < state.total
}

async function runSearch(row: DesignArtifactRelationshipType) {
  const propertyName = draftSearchProperty.value[row.key]
  const propertyValue = draftSearchValue.value[row.key] ?? ''
  if (!propertyName || !propertyValue.trim()) return
  await searchRelationshipInstances(row.key, {
    relationshipType: row.relationship_type,
    sourceEntityType: row.source_entity_type,
    targetEntityType: row.target_entity_type,
    propertyName,
    propertyValue: propertyValue.trim(),
  })
}

async function resetSearch(row: DesignArtifactRelationshipType) {
  draftSearchValue.value[row.key] = ''
  await clearRelationshipSearch(row.key, {
    relationshipType: row.relationship_type,
    sourceEntityType: row.source_entity_type,
    targetEntityType: row.target_entity_type,
    seedInstances: row.instances ?? [],
    total: row.instance_count,
  })
}

async function loadMore(row: DesignArtifactRelationshipType) {
  await loadMoreRelationshipInstances(row.key, {
    relationshipType: row.relationship_type,
    sourceEntityType: row.source_entity_type,
    targetEntityType: row.target_entity_type,
  })
}
</script>

<template>
  <div class="space-y-1.5">
    <Card
      v-for="rel in rows"
      :key="rel.key"
      :class="['overflow-hidden', prepopulationCardClass(rel.prepopulated_instances)]"
    >
      <details class="group">
        <summary
          class="flex cursor-pointer list-none items-start gap-2 px-2.5 py-2 [&::-webkit-details-marker]:hidden"
        >
          <ChevronDown
            class="mt-0.5 size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
          />
          <div class="min-w-0 flex-1 space-y-0.5">
            <div class="flex min-w-0 flex-wrap items-center gap-1.5">
              <span class="text-sm font-semibold leading-tight text-foreground">{{
                rel.source_entity_type
              }}</span>
              <Badge variant="secondary" class="h-5 px-1.5 font-mono text-[10px]">{{
                rel.relationship_type
              }}</Badge>
              <template v-if="rel.reverse_relationship_type">
                <span class="text-[10px] text-muted-foreground">/</span>
                <Badge variant="outline" class="h-5 px-1.5 font-mono text-[10px]">{{
                  rel.reverse_relationship_type
                }}</Badge>
              </template>
              <Badge
                variant="outline"
                class="h-5 px-1.5 text-[10px]"
                :class="prepopulationBadgeClass(rel.prepopulated_instances)"
              >
                {{ prepopulationLabel(rel.prepopulated_instances) }}
              </Badge>
              <span class="text-xs text-muted-foreground">→</span>
              <span class="text-sm font-semibold leading-tight text-foreground">{{
                rel.target_entity_type
              }}</span>
              <Badge variant="outline" class="h-5 px-1.5 text-[10px]">
                {{ rel.instance_count }} instance{{ rel.instance_count === 1 ? '' : 's' }}
              </Badge>
            </div>
            <p class="truncate font-mono text-[10px] text-muted-foreground">{{ rel.key }}</p>
          </div>
        </summary>
        <div class="space-y-2 border-t px-2.5 pb-2.5 pt-0">
          <p v-if="rel.description" class="pt-2 text-xs leading-snug text-muted-foreground">
            {{ rel.description }}
          </p>
          <div v-else class="pt-1.5 text-xs italic text-muted-foreground">No description</div>

          <div class="space-y-1">
            <p class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Parameters
            </p>
            <div
              v-if="rel.parameter_definitions && Object.keys(rel.parameter_definitions).length > 0"
              class="divide-y rounded-md border text-xs"
            >
              <div
                v-for="(label, key) in rel.parameter_definitions"
                :key="key"
                class="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 px-2 py-1"
              >
                <code class="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">{{ key }}</code>
                <span class="text-muted-foreground">{{ label }}</span>
                <Badge
                  v-if="rel.required_parameters?.includes(String(key))"
                  variant="outline"
                  class="h-4 px-1 text-[9px]"
                >
                  required
                </Badge>
                <Badge
                  v-else-if="rel.optional_parameters?.includes(String(key))"
                  variant="outline"
                  class="h-4 px-1 text-[9px] opacity-70"
                >
                  optional
                </Badge>
              </div>
            </div>
            <p v-else class="text-xs text-muted-foreground">No parameter definitions</p>
          </div>

          <details v-if="rel.instance_count > 0" class="group/inst rounded-md border">
            <summary
              class="flex cursor-pointer list-none items-center gap-1.5 px-2 py-1.5 text-xs font-medium hover:bg-muted/50 [&::-webkit-details-marker]:hidden"
            >
              <ChevronDown
                class="size-3.5 shrink-0 text-muted-foreground transition-transform group-open/inst:rotate-180"
              />
              Instances
              <span class="font-normal text-muted-foreground">
                (showing {{ ensureRelationshipState(rel.key).instances.length }} of
                {{ ensureRelationshipState(rel.key).total }})
              </span>
            </summary>
            <div class="space-y-2 border-t p-2">
              <div class="flex flex-wrap items-end gap-2" @click.stop>
                <div class="min-w-[8rem] flex-1 space-y-1">
                  <label class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    Property
                  </label>
                  <Select v-model="draftSearchProperty[rel.key]">
                    <SelectTrigger class="h-8 text-xs">
                      <SelectValue placeholder="Select property" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem
                        v-for="prop in searchableRelationshipProperties(rel)"
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
                    v-model="draftSearchValue[rel.key]"
                    class="h-8 text-xs"
                    placeholder="Contains…"
                    @keydown.enter.prevent="runSearch(rel)"
                  />
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  class="h-8 px-2 text-xs"
                  :disabled="relationshipStates[rel.key]?.loading"
                  @click.stop.prevent="runSearch(rel)"
                >
                  <Loader2 v-if="relationshipStates[rel.key]?.loading" class="mr-1 size-3.5 animate-spin" />
                  <Search v-else class="mr-1 size-3.5" />
                  Search
                </Button>
                <Button
                  v-if="relationshipStates[rel.key]?.activeSearch"
                  variant="ghost"
                  size="sm"
                  class="h-8 px-2 text-xs"
                  @click.stop.prevent="resetSearch(rel)"
                >
                  <X class="mr-1 size-3.5" />
                  Clear
                </Button>
              </div>

              <ul class="space-y-1 text-xs">
                <li
                  v-for="(inst, idx) in ensureRelationshipState(rel.key).instances"
                  :key="`${rel.key}-${idx}`"
                  class="rounded-md bg-muted/40 px-2 py-1"
                >
                  <div class="mb-0.5 font-mono text-[10px] text-muted-foreground">
                    {{ inst.source_slug }} --{{ rel.relationship_type }}--> {{ inst.target_slug }}
                  </div>
                  <pre class="max-h-24 overflow-y-auto whitespace-pre-wrap break-all text-[10px] leading-snug">{{
                    JSON.stringify(inst.properties ?? {}, null, 2)
                  }}</pre>
                </li>
              </ul>

              <p
                v-if="ensureRelationshipState(rel.key).instances.length === 0"
                class="text-xs text-muted-foreground"
              >
                No instances match the current filter.
              </p>

              <div v-if="canLoadMore(rel)" class="flex flex-wrap items-center gap-1.5" @click.stop>
                <Button
                  variant="outline"
                  size="sm"
                  class="h-7 px-2 text-xs"
                  :disabled="relationshipStates[rel.key]?.loading"
                  @click.stop.prevent="loadMore(rel)"
                >
                  <Loader2 v-if="relationshipStates[rel.key]?.loading" class="mr-1 size-3.5 animate-spin" />
                  Load next {{ DESIGN_ARTIFACT_INSTANCE_PAGE_SIZE }}
                </Button>
                <span class="text-xs text-muted-foreground">
                  {{ ensureRelationshipState(rel.key).instances.length }} loaded ·
                  {{ ensureRelationshipState(rel.key).total - ensureRelationshipState(rel.key).instances.length }}
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
