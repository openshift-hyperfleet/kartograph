<script setup lang="ts">
import {
  Cable,
  Building2,
  Github,
} from 'lucide-vue-next'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'

const { hasTenant } = useTenant()

// Adapter types that will be supported — shown as a preview
const adapters = [
  { id: 'github', label: 'GitHub', description: 'Repositories, issues, pull requests, and code', icon: Github, available: false },
]
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
      <Badge variant="secondary" class="text-xs">Coming Soon</Badge>
    </div>

    <Separator />

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view data sources.</p>
    </div>

    <template v-else>
      <!-- Coming soon state with adapter preview -->
      <div class="flex flex-col items-center gap-4 py-12 text-center">
        <div class="rounded-full bg-muted p-5">
          <Cable class="size-10 text-muted-foreground" />
        </div>
        <div class="space-y-1">
          <h2 class="text-lg font-semibold">Data Sources — Coming Soon</h2>
          <p class="max-w-md text-sm text-muted-foreground">
            Connect data sources to your knowledge graphs. Supported adapters will fetch raw content,
            which is then processed by the AI extraction pipeline to produce graph entities and relationships.
          </p>
        </div>
      </div>

      <!-- Adapter preview cards -->
      <div>
        <h2 class="mb-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Planned Adapters
        </h2>
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Card
            v-for="adapter in adapters"
            :key="adapter.id"
            class="opacity-60"
          >
            <CardContent class="flex items-start gap-3 p-4">
              <div class="rounded-md bg-muted p-2 shrink-0">
                <component :is="adapter.icon" class="size-4 text-muted-foreground" />
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <p class="text-sm font-medium">{{ adapter.label }}</p>
                  <Badge variant="outline" class="text-[10px] px-1.5 py-0">Soon</Badge>
                </div>
                <p class="text-xs text-muted-foreground mt-0.5">{{ adapter.description }}</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </template>
  </div>
</template>
