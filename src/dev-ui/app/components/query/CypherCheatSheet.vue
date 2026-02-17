<script setup lang="ts">
import { ref } from 'vue'
import { ChevronDown, ChevronRight, ArrowDownToLine } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

const emit = defineEmits<{
  'insert-at-cursor': [pattern: string]
}>()

interface CheatSection {
  title: string
  defaultOpen: boolean
  items: { pattern: string; description: string }[]
}

const sections: CheatSection[] = [
  {
    title: 'Node Patterns',
    defaultOpen: false,
    items: [
      { pattern: '(n)', description: 'Any node' },
      { pattern: '(n:Label)', description: 'Node with label' },
      { pattern: '(n:Label {prop: val})', description: 'Node with property' },
      { pattern: '(:Label)', description: 'Anonymous node' },
    ],
  },
  {
    title: 'Relationship Patterns',
    defaultOpen: false,
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
    defaultOpen: true,
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
    defaultOpen: false,
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
    defaultOpen: false,
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
    defaultOpen: false,
    items: [
      { pattern: 'RETURN {a: v1, b: v2}', description: 'Single column only — use map syntax' },
      { pattern: 'No OPTIONAL MATCH', description: 'Use WHERE + IS NOT NULL instead' },
      { pattern: 'No UNION / CALL / YIELD', description: 'Run separate queries' },
      { pattern: 'No list comprehensions', description: 'Use UNWIND + COLLECT instead' },
    ],
  },
]

const openSections = ref<Set<string>>(
  new Set(sections.filter((s) => s.defaultOpen).map((s) => s.title)),
)

function toggleSection(title: string) {
  if (openSections.value.has(title)) {
    openSections.value.delete(title)
  } else {
    openSections.value.add(title)
  }
  // Trigger reactivity
  openSections.value = new Set(openSections.value)
}

function handleInsert(pattern: string) {
  emit('insert-at-cursor', pattern)
}
</script>

<template>
  <TooltipProvider :delay-duration="300">
    <div class="space-y-1">
      <div v-for="section in sections" :key="section.title">
        <!-- Section header (collapsible toggle) -->
        <button
          class="flex w-full items-center gap-1.5 rounded px-1 py-1 text-left transition-colors hover:bg-muted/50"
          @click="toggleSection(section.title)"
        >
          <ChevronDown
            v-if="openSections.has(section.title)"
            class="size-3 shrink-0 text-muted-foreground"
          />
          <ChevronRight
            v-else
            class="size-3 shrink-0 text-muted-foreground"
          />
          <span class="text-xs font-semibold text-muted-foreground">{{ section.title }}</span>
          <Badge
            v-if="section.title === 'Apache AGE Notes'"
            variant="warning"
            class="h-4 px-1 text-[10px]"
          >
            Important
          </Badge>
        </button>

        <!-- Collapsible section content -->
        <div v-if="openSections.has(section.title)" class="space-y-0.5 pb-1 pl-[18px]">
          <Tooltip v-for="item in section.items" :key="item.pattern">
            <TooltipTrigger as-child>
              <button
                class="group flex w-full items-center gap-2 rounded px-1 py-0.5 text-left transition-colors hover:bg-muted/70"
                @click="handleInsert(item.pattern)"
              >
                <code class="min-w-0 truncate rounded bg-muted px-1 py-0.5 font-mono text-[10px] transition-colors group-hover:bg-primary/15 group-hover:text-primary">
                  {{ item.pattern }}
                </code>
                <span class="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">
                  {{ item.description }}
                </span>
                <ArrowDownToLine
                  class="size-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                />
              </button>
            </TooltipTrigger>
            <TooltipContent side="left" :side-offset="8">
              <p class="text-xs">Click to insert into editor</p>
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
    </div>
  </TooltipProvider>
</template>
