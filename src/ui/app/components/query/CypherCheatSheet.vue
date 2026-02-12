<script setup lang="ts">
import { ref } from 'vue'
import { ChevronDown, ChevronRight, BookOpen } from 'lucide-vue-next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const isOpen = ref(false)

interface CheatSection {
  title: string
  items: { pattern: string; description: string }[]
}

const sections: CheatSection[] = [
  {
    title: 'Node Patterns',
    items: [
      { pattern: '(n)', description: 'Any node' },
      { pattern: '(n:Label)', description: 'Node with label' },
      { pattern: '(n:Label {prop: val})', description: 'Node with property' },
      { pattern: '(:Label)', description: 'Anonymous node' },
    ],
  },
  {
    title: 'Relationship Patterns',
    items: [
      { pattern: '-[r]->', description: 'Directed relationship' },
      { pattern: '-[r:TYPE]->', description: 'Typed relationship' },
      { pattern: '-[r]-', description: 'Undirected' },
      { pattern: '-[r*1..3]->', description: 'Variable length (1-3 hops)' },
      { pattern: '-[r*]->', description: 'Any length path' },
    ],
  },
  {
    title: 'Common Clauses',
    items: [
      { pattern: 'MATCH (n) RETURN n', description: 'Find and return nodes' },
      { pattern: 'WHERE n.prop = val', description: 'Filter results' },
      { pattern: 'ORDER BY n.prop DESC', description: 'Sort results' },
      { pattern: 'LIMIT 25', description: 'Limit result count' },
      { pattern: 'SKIP 10', description: 'Skip results (pagination)' },
      { pattern: 'WITH n, count(*) AS cnt', description: 'Chain query parts' },
      { pattern: 'UNWIND [1,2,3] AS x', description: 'Expand list to rows' },
    ],
  },
  {
    title: 'Operators',
    items: [
      { pattern: '=, <>, <, >, <=, >=', description: 'Comparison' },
      { pattern: 'AND, OR, NOT, XOR', description: 'Logical' },
      { pattern: 'IN [val1, val2]', description: 'List membership' },
      { pattern: 'IS NULL / IS NOT NULL', description: 'Null check' },
      { pattern: 'STARTS WITH, ENDS WITH', description: 'String prefix/suffix' },
      { pattern: 'CONTAINS', description: 'String contains' },
      { pattern: '=~', description: 'Regex match' },
    ],
  },
  {
    title: 'Useful Functions',
    items: [
      { pattern: 'labels(n)', description: 'Node labels' },
      { pattern: 'type(r)', description: 'Relationship type' },
      { pattern: 'properties(n)', description: 'All properties as map' },
      { pattern: 'count(*)', description: 'Count results' },
      { pattern: 'collect(n.prop)', description: 'Collect into list' },
      { pattern: 'coalesce(a, b)', description: 'First non-null' },
      { pattern: 'size(list)', description: 'List/string size' },
      { pattern: 'keys(n)', description: 'Property keys' },
    ],
  },
  {
    title: 'Apache AGE Notes',
    items: [
      { pattern: 'RETURN {a: v1, b: v2}', description: 'Single column only — use map syntax' },
      { pattern: 'No OPTIONAL MATCH', description: 'Use WHERE + IS NOT NULL instead' },
      { pattern: 'No UNION / CALL / YIELD', description: 'Run separate queries' },
      { pattern: 'No list comprehensions', description: 'Use UNWIND + COLLECT instead' },
    ],
  },
]
</script>

<template>
  <Card class="flex flex-col">
    <CardHeader
      class="cursor-pointer pb-3"
      @click="isOpen = !isOpen"
    >
      <div class="flex items-center justify-between">
        <CardTitle class="flex items-center gap-1.5 text-sm font-medium">
          <BookOpen class="size-3.5" />
          Cheat Sheet
        </CardTitle>
        <ChevronDown v-if="isOpen" class="size-4 text-muted-foreground" />
        <ChevronRight v-else class="size-4 text-muted-foreground" />
      </div>
    </CardHeader>
    <CardContent v-if="isOpen" class="max-h-96 overflow-y-auto pt-0">
      <div class="space-y-4">
        <div v-for="section in sections" :key="section.title">
          <div class="mb-1.5 flex items-center gap-1.5">
            <span class="text-xs font-semibold text-muted-foreground">{{ section.title }}</span>
            <Badge
              v-if="section.title === 'Apache AGE Notes'"
              variant="warning"
              class="h-4 px-1 text-[9px]"
            >
              Important
            </Badge>
          </div>
          <div class="space-y-1">
            <div
              v-for="item in section.items"
              :key="item.pattern"
              class="flex items-start gap-2 text-[11px]"
            >
              <code class="shrink-0 rounded bg-muted px-1 py-0.5 font-mono text-[10px]">
                {{ item.pattern }}
              </code>
              <span class="text-muted-foreground">{{ item.description }}</span>
            </div>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
