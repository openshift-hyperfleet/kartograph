<script setup lang="ts">
/**
 * WorkspaceGuidance
 *
 * Displayed on the home page when the authenticated user belongs to a tenant
 * but has no personal workspace yet. Prompts them to either create a workspace
 * or contact a workspace admin to be added to an existing team workspace.
 *
 * Spec: specs/ui/experience.spec.md — "Workspace guidance" scenario
 * Task: task-062
 */
import { FolderTree, Plus, Users } from 'lucide-vue-next'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const emit = defineEmits<{
  /** Emitted when the user clicks "Create Workspace" */
  create: []
  /** Emitted when the user clicks "Join a Team Workspace" */
  join: []
}>()
</script>

<template>
  <Card data-testid="workspace-guidance" class="border-primary/20 bg-primary/5">
    <CardContent class="flex flex-col items-center gap-6 py-12 text-center">
      <!-- Icon -->
      <div class="rounded-full bg-primary/10 p-4">
        <FolderTree class="size-8 text-primary" />
      </div>

      <!-- Heading and description -->
      <div class="max-w-sm">
        <h2 class="text-xl font-semibold tracking-tight">
          Get started with your first workspace
        </h2>
        <p class="mt-2 text-sm text-muted-foreground">
          Workspaces help you organise knowledge graphs and control access for your team.
          Create your own workspace or ask a team member to add you to an existing one.
        </p>
      </div>

      <!-- Primary actions -->
      <div class="flex flex-wrap items-center justify-center gap-3">
        <Button data-testid="btn-create-workspace" @click="emit('create')">
          <Plus class="mr-2 size-4" />
          Create Workspace
        </Button>
        <Button
          variant="outline"
          data-testid="btn-join-workspace"
          @click="emit('join')"
        >
          <Users class="mr-2 size-4" />
          Join a Team Workspace
        </Button>
      </div>
    </CardContent>
  </Card>
</template>
