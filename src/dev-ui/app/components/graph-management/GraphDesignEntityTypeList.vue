<script setup lang="ts">
import { ChevronDown } from 'lucide-vue-next'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  type DesignArtifactEntityType,
  pageSlice,
  prepopulationBadgeClass,
  prepopulationCardClass,
  prepopulationLabel,
} from '@/utils/kgDesignArtifacts'

defineProps<{
  rows: DesignArtifactEntityType[]
  instancePage: Record<string, number>
}>()

const emit = defineEmits<{
  'update:instancePage': [key: string, page: number]
}>()
</script>

<template>
  <div class="space-y-1.5">
    <Card
      v-for="row in rows"
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

          <details v-if="(row.instances?.length ?? 0) > 0" class="group/inst rounded-md border">
            <summary
              class="flex cursor-pointer list-none items-center gap-1.5 px-2 py-1.5 text-xs font-medium hover:bg-muted/50 [&::-webkit-details-marker]:hidden"
            >
              <ChevronDown
                class="size-3.5 shrink-0 text-muted-foreground transition-transform group-open/inst:rotate-180"
              />
              Instances
              <span v-if="row.instances_truncated" class="font-normal text-muted-foreground">
                (showing {{ row.instances_returned ?? row.instances?.length ?? 0 }} of
                {{ row.instance_count }})
              </span>
            </summary>
            <div class="space-y-2 border-t p-2">
              <ul class="space-y-1 text-xs">
                <li
                  v-for="(inst, idx) in pageSlice(instancePage, row.type, row.instances || []).items"
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
              <div
                v-if="pageSlice(instancePage, row.type, row.instances || []).total > 20"
                class="flex flex-wrap items-center gap-1.5"
                @click.stop
              >
                <Button
                  variant="outline"
                  size="sm"
                  class="h-7 px-2 text-xs"
                  :disabled="pageSlice(instancePage, row.type, row.instances || []).page <= 0"
                  @click.stop.prevent="emit('update:instancePage', row.type, pageSlice(instancePage, row.type, row.instances || []).page - 1)"
                >
                  Previous
                </Button>
                <span class="text-xs text-muted-foreground">
                  Page {{ pageSlice(instancePage, row.type, row.instances || []).page + 1 }} /
                  {{ pageSlice(instancePage, row.type, row.instances || []).totalPages }}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  class="h-7 px-2 text-xs"
                  :disabled="
                    pageSlice(instancePage, row.type, row.instances || []).page
                      >= pageSlice(instancePage, row.type, row.instances || []).totalPages - 1
                  "
                  @click.stop.prevent="emit('update:instancePage', row.type, pageSlice(instancePage, row.type, row.instances || []).page + 1)"
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
