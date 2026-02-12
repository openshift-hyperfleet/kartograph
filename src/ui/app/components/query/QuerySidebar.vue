<script setup lang="ts">
import {
  Database, Sparkles, BookOpen, Clock,
} from 'lucide-vue-next'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import type { HistoryEntry } from '~/types'

import QueryTemplates from '@/components/query/QueryTemplates.vue'
import CypherCheatSheet from '@/components/query/CypherCheatSheet.vue'
import SchemaPanel from '@/components/query/SchemaPanel.vue'
import HistoryPanel from '@/components/query/HistoryPanel.vue'

const props = defineProps<{
  nodeLabels: string[]
  edgeLabels: string[]
  schemaLoading: boolean
  history: HistoryEntry[]
  currentQuery: string
}>()

const emit = defineEmits<{
  'select-query': [query: string]
  'insert-at-cursor': [text: string]
  'clear-history': []
  'execute-query': [query: string]
}>()
</script>

<template>
  <Tabs default-value="history" class="flex h-full min-w-0 flex-col">
    <TabsList class="w-full shrink-0">
      <TabsTrigger value="history" class="gap-1 text-xs">
        <Clock class="size-3.5 shrink-0" />
        <span class="truncate">History</span>
        <Badge
          v-if="history.length > 0"
          variant="secondary"
          class="h-4 shrink-0 px-1 text-[10px]"
        >
          {{ history.length }}
        </Badge>
      </TabsTrigger>

      <TabsTrigger value="schema" class="gap-1 text-xs">
        <Database class="size-3.5 shrink-0" />
        <span class="truncate">Schema</span>
      </TabsTrigger>

      <TabsTrigger value="templates" class="gap-1 text-xs">
        <Sparkles class="size-3.5 shrink-0" />
        <span class="truncate">Templates</span>
      </TabsTrigger>

      <TabsTrigger value="reference" class="gap-1 text-xs">
        <BookOpen class="size-3.5 shrink-0" />
        <span class="truncate">Ref</span>
      </TabsTrigger>
    </TabsList>

    <!-- History Tab (primary) -->
    <TabsContent value="history" class="min-h-0 min-w-0 flex-1 overflow-y-auto">
      <HistoryPanel
        :history="history"
        :current-query="currentQuery"
        @select-query="(q: string) => emit('select-query', q)"
        @clear-history="emit('clear-history')"
      />
    </TabsContent>

    <!-- Schema Tab -->
    <TabsContent value="schema" class="min-h-0 min-w-0 flex-1 overflow-y-auto p-1">
      <SchemaPanel
        :node-labels="nodeLabels"
        :edge-labels="edgeLabels"
        :schema-loading="schemaLoading"
        @execute-query="(q: string) => emit('execute-query', q)"
        @insert-at-cursor="(t: string) => emit('insert-at-cursor', t)"
      />
    </TabsContent>

    <!-- Templates Tab -->
    <TabsContent value="templates" class="min-h-0 min-w-0 flex-1 overflow-y-auto p-1">
      <QueryTemplates
        :node-labels="nodeLabels"
        :edge-labels="edgeLabels"
        @select-query="(q: string) => emit('select-query', q)"
      />
    </TabsContent>

    <!-- Reference Tab -->
    <TabsContent value="reference" class="min-h-0 min-w-0 flex-1 overflow-y-auto p-1">
      <CypherCheatSheet
        @insert-at-cursor="(t: string) => emit('insert-at-cursor', t)"
      />
    </TabsContent>
  </Tabs>
</template>
