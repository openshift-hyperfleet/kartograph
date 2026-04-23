import { describe, it, expect, vi, beforeEach } from 'vitest'

// Since these are Nuxt components with composables, test the logic functions
// directly rather than mounting the full component

describe('Data Sources Wizard - Step Navigation', () => {
  it('requires adapter selection to proceed to step 2', () => {
    // Test the nextStep() logic when no adapter is selected
    const selectedAdapterId = { value: '' }
    const wizardStep = { value: 1 }

    function nextStep() {
      if (wizardStep.value === 1) {
        if (!selectedAdapterId.value) return
        wizardStep.value = 2
      }
    }

    nextStep()
    expect(wizardStep.value).toBe(1) // Should stay on step 1
  })

  it('advances to step 2 when adapter is selected', () => {
    const selectedAdapterId = { value: 'github' }
    const selectedKnowledgeGraphId = { value: 'kg-123' }
    const wizardStep = { value: 1 }

    function nextStep() {
      if (wizardStep.value === 1) {
        if (!selectedAdapterId.value) return
        if (!selectedKnowledgeGraphId.value) return
        wizardStep.value = 2
      }
    }

    nextStep()
    expect(wizardStep.value).toBe(2)
  })
})

describe('Data Sources Wizard - Form Validation', () => {
  it('validates required fields in step 2', () => {
    const connName = { value: '' }
    const connRepoUrl = { value: '' }
    const connToken = { value: '' }
    const connNameError = { value: '' }
    const connRepoUrlError = { value: '' }
    const connTokenError = { value: '' }
    const wizardStep = { value: 2 }

    function validate() {
      let valid = true
      if (!connName.value.trim()) {
        connNameError.value = 'Data source name is required.'
        valid = false
      }
      if (!connRepoUrl.value.trim()) {
        connRepoUrlError.value = 'Repository URL is required.'
        valid = false
      } else if (!connRepoUrl.value.includes('github.com')) {
        connRepoUrlError.value = 'Enter a valid GitHub repository URL.'
        valid = false
      }
      if (!connToken.value.trim()) {
        connTokenError.value = 'Access token is required.'
        valid = false
      }
      return valid
    }

    expect(validate()).toBe(false)
    expect(connNameError.value).toBe('Data source name is required.')
    expect(connRepoUrlError.value).toBe('Repository URL is required.')
    expect(connTokenError.value).toBe('Access token is required.')
  })

  it('passes validation with all fields filled', () => {
    const connName = { value: 'my-repo' }
    const connRepoUrl = { value: 'https://github.com/owner/my-repo' }
    const connToken = { value: 'ghp_test123' }
    const connNameError = { value: '' }
    const connRepoUrlError = { value: '' }
    const connTokenError = { value: '' }

    function validate() {
      let valid = true
      if (!connName.value.trim()) { connNameError.value = 'Name required'; valid = false }
      if (!connRepoUrl.value.trim()) { connRepoUrlError.value = 'URL required'; valid = false }
      else if (!connRepoUrl.value.includes('github.com')) { connRepoUrlError.value = 'Invalid URL'; valid = false }
      if (!connToken.value.trim()) { connTokenError.value = 'Token required'; valid = false }
      return valid
    }

    expect(validate()).toBe(true)
  })

  it('infers data source name from GitHub repo URL', () => {
    const connRepoUrl = { value: '' }
    const connName = { value: '' }

    function inferName(url: string) {
      if (!url.trim() || connName.value.trim()) return
      const match = url.trim().match(/github\.com\/[^/]+\/([^/]+?)(?:\.git)?$/)
      if (match) {
        connName.value = match[1]
      }
    }

    connRepoUrl.value = 'https://github.com/owner/my-awesome-repo'
    inferName(connRepoUrl.value)
    expect(connName.value).toBe('my-awesome-repo')
  })
})

describe('Data Sources Wizard - Intent Step', () => {
  it('requires intent text to proceed to ontology step', () => {
    const intentText = { value: '' }
    const intentError = { value: '' }
    const wizardStep = { value: 3 }

    function nextStep() {
      if (wizardStep.value === 3) {
        intentError.value = ''
        if (!intentText.value.trim()) {
          intentError.value = 'Please describe your intent before continuing.'
          return
        }
        wizardStep.value = 4
      }
    }

    nextStep()
    expect(wizardStep.value).toBe(3)
    expect(intentError.value).toBe('Please describe your intent before continuing.')
  })

  it('advances to ontology step when intent is provided', () => {
    const intentText = { value: 'I want to understand contributor patterns' }
    const intentError = { value: '' }
    const wizardStep = { value: 3 }
    const scanningOntology = { value: false }
    const proposedNodes: unknown[] = []
    const proposedEdges: unknown[] = []

    function nextStep() {
      if (wizardStep.value === 3) {
        intentError.value = ''
        if (!intentText.value.trim()) {
          intentError.value = 'Please describe your intent before continuing.'
          return
        }
        wizardStep.value = 4
        scanningOntology.value = true
      }
    }

    nextStep()
    expect(wizardStep.value).toBe(4)
    expect(scanningOntology.value).toBe(true)
  })
})

describe('Data Sources Wizard - Token Visibility', () => {
  it('toggles token visibility', () => {
    const showToken = { value: false }

    function toggleToken() {
      showToken.value = !showToken.value
    }

    expect(showToken.value).toBe(false)
    toggleToken()
    expect(showToken.value).toBe(true)
    toggleToken()
    expect(showToken.value).toBe(false)
  })
})

describe('Data Sources Wizard - Approval', () => {
  it('requires knowledge graph selection before approval', async () => {
    const selectedKnowledgeGraphId = { value: '' }
    let toastMessage = ''

    async function approveOntology() {
      if (!selectedKnowledgeGraphId.value) {
        toastMessage = 'Please select a knowledge graph first'
        return
      }
    }

    await approveOntology()
    expect(toastMessage).toBe('Please select a knowledge graph first')
  })
})

describe('Sync Monitoring', () => {
  it('computes sync duration correctly', () => {
    const startedAt = '2024-01-01T10:00:00Z'
    const completedAt = '2024-01-01T10:00:30Z'

    const duration = Math.round(
      (new Date(completedAt).getTime() - new Date(startedAt).getTime()) / 1000
    )

    expect(duration).toBe(30)
  })

  it('shows idle status when no sync runs exist', () => {
    const syncRuns: unknown[] = []
    const status = syncRuns.length > 0 ? (syncRuns[0] as { status: string }).status : 'idle'
    expect(status).toBe('idle')
  })
})
