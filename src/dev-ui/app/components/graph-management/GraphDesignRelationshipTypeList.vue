<script setup lang="ts">
import { ChevronDown } from 'lucide-vue-next'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  type DesignArtifactRelationshipType,
  pageSlice,
  prepopulationBadgeClass,
  prepopulationCardClass,
  prepopulationLabel,
} from '@/utils/kgDesignArtifacts'

defineProps<{
  rows: DesignArtifactRelationshipType[]
  instancePage: Record<string, number>
}>()

const emit = defineEmits<{
  'update:instancePage': [key: string, page: number]
}>()
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
              </div>
            </div>
            <p v-else class="text-xs text-muted-foreground">No parameter definitions</p>
          </div>

          <details v-if="rel.instances.length > 0" class="group/inst rounded-md border">
            <summary
              class="flex cursor-pointer list-none items-center gap-1.5 px-2 py-1.5 text-xs font-medium hover:bg-muted/50 [&::-webkit-details-marker]:hidden"
            >
              <ChevronDown
                class="size-3.5 shrink-0 text-muted-foreground transition-transform group-open/inst:rotate-180"
              />
              Instances
              <span v-if="rel.instances_truncated" class="font-normal text-muted-foreground">
                (showing {{ rel.instances_returned ?? rel.instances.length }} of
                {{ rel.instance_count }})
              </span>
            </summary>
            <div class="space-y-2 border-t p-2">
              <ul class="space-y-1 text-xs">
                <li
                  v-for="(inst, idx) in pageSlice(instancePage, rel.key, rel.instances).items"
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
              <div
                v-if="pageSlice(instancePage, rel.key, rel.instances).total > 20"
                class="flex flex-wrap items-center gap-1.5"
                @click.stop
              >
                <Button
                  variant="outline"
                  size="sm"
                  class="h-7 px-2 text-xs"
                  :disabled="pageSlice(instancePage, rel.key, rel.instances).page <= 0"
                  @click.stop.prevent="emit('update:instancePage', rel.key, pageSlice(instancePage, rel.key, rel.instances).page - 1)"
                >
                  Previous
                </Button>
                <span class="text-xs text-muted-foreground">
                  Page {{ pageSlice(instancePage, rel.key, rel.instances).page + 1 }} /
                  {{ pageSlice(instancePage, rel.key, rel.instances).totalPages }}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  class="h-7 px-2 text-xs"
                  :disabled="
                    pageSlice(instancePage, rel.key, rel.instances).page
                      >= pageSlice(instancePage, rel.key, rel.instances).totalPages - 1
                  "
                  @click.stop.prevent="emit('update:instancePage', rel.key, pageSlice(instancePage, rel.key, rel.instances).page + 1)"
                >
                  Next
                </Button>
              </div>
            </div>
          </details>
        </div>
      </details>
    </Card>
  </div>
</template>
