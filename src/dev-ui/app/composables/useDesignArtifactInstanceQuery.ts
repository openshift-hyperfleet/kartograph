import { reactive, watch, type Ref } from 'vue'
import {
  type DesignArtifactInstance,
  DESIGN_ARTIFACT_INSTANCE_PAGE_SIZE,
} from '@/utils/kgDesignArtifacts'

export interface DesignArtifactInstanceQueryState {
  instances: DesignArtifactInstance[]
  total: number
  loading: boolean
  searchProperty: string
  searchValue: string
  activeSearch: boolean
}

function emptyState(): DesignArtifactInstanceQueryState {
  return {
    instances: [],
    total: 0,
    loading: false,
    searchProperty: '',
    searchValue: '',
    activeSearch: false,
  }
}

export function useDesignArtifactInstanceQuery(kgId: Ref<string>, resetNonce: Ref<number>) {
  const { apiFetch } = useApiClient()
  const entityStates = reactive<Record<string, DesignArtifactInstanceQueryState>>({})
  const relationshipStates = reactive<Record<string, DesignArtifactInstanceQueryState>>({})

  watch([kgId, resetNonce], () => {
    for (const key of Object.keys(entityStates)) delete entityStates[key]
    for (const key of Object.keys(relationshipStates)) delete relationshipStates[key]
  })

  function ensureEntityState(
    key: string,
    seed?: { instances?: DesignArtifactInstance[]; total?: number },
  ): DesignArtifactInstanceQueryState {
    if (!entityStates[key]) {
      entityStates[key] = {
        ...emptyState(),
        instances: [...(seed?.instances ?? [])],
        total: seed?.total ?? seed?.instances?.length ?? 0,
      }
    }
    return entityStates[key]
  }

  function ensureRelationshipState(
    key: string,
    seed?: { instances?: DesignArtifactInstance[]; total?: number },
  ): DesignArtifactInstanceQueryState {
    if (!relationshipStates[key]) {
      relationshipStates[key] = {
        ...emptyState(),
        instances: [...(seed?.instances ?? [])],
        total: seed?.total ?? seed?.instances?.length ?? 0,
      }
    }
    return relationshipStates[key]
  }

  async function fetchEntityInstances(
    key: string,
    params: {
      entityType: string
      offset: number
      propertyName?: string
      propertyValue?: string
    },
  ) {
    const state = ensureEntityState(key)
    state.loading = true
    try {
      const result = await apiFetch<{
        instances: DesignArtifactInstance[]
        total: number
      }>(`/management/knowledge-graphs/${kgId.value}/design-artifacts/entity-instances`, {
        query: {
          entity_type: params.entityType,
          limit: DESIGN_ARTIFACT_INSTANCE_PAGE_SIZE,
          offset: params.offset,
          ...(params.propertyName && params.propertyValue !== undefined
            ? { property_name: params.propertyName, property_value: params.propertyValue }
            : {}),
        },
      })
      return result
    } finally {
      state.loading = false
    }
  }

  async function fetchRelationshipInstances(
    key: string,
    params: {
      relationshipType: string
      sourceEntityType: string
      targetEntityType: string
      offset: number
      propertyName?: string
      propertyValue?: string
    },
  ) {
    const state = ensureRelationshipState(key)
    state.loading = true
    try {
      return await apiFetch<{
        instances: DesignArtifactInstance[]
        total: number
      }>(`/management/knowledge-graphs/${kgId.value}/design-artifacts/relationship-instances`, {
        query: {
          relationship_type: params.relationshipType,
          source_entity_type: params.sourceEntityType,
          target_entity_type: params.targetEntityType,
          limit: DESIGN_ARTIFACT_INSTANCE_PAGE_SIZE,
          offset: params.offset,
          ...(params.propertyName && params.propertyValue !== undefined
            ? { property_name: params.propertyName, property_value: params.propertyValue }
            : {}),
        },
      })
    } finally {
      state.loading = false
    }
  }

  async function searchEntityInstances(
    key: string,
    params: { entityType: string; propertyName: string; propertyValue: string },
  ) {
    const state = ensureEntityState(key)
    state.searchProperty = params.propertyName
    state.searchValue = params.propertyValue
    state.activeSearch = true
    const result = await fetchEntityInstances(key, {
      entityType: params.entityType,
      offset: 0,
      propertyName: params.propertyName,
      propertyValue: params.propertyValue,
    })
    state.instances = result.instances
    state.total = result.total
  }

  async function clearEntitySearch(
    key: string,
    params: { entityType: string; seedInstances: DesignArtifactInstance[]; total: number },
  ) {
    const state = ensureEntityState(key)
    state.searchProperty = ''
    state.searchValue = ''
    state.activeSearch = false
    state.instances = [...params.seedInstances]
    state.total = params.total
  }

  async function loadMoreEntityInstances(key: string, params: { entityType: string }) {
    const state = ensureEntityState(key)
    const result = await fetchEntityInstances(key, {
      entityType: params.entityType,
      offset: state.instances.length,
      propertyName: state.activeSearch ? state.searchProperty : undefined,
      propertyValue: state.activeSearch ? state.searchValue : undefined,
    })
    state.instances = [...state.instances, ...result.instances]
    state.total = result.total
  }

  async function searchRelationshipInstances(
    key: string,
    params: {
      relationshipType: string
      sourceEntityType: string
      targetEntityType: string
      propertyName: string
      propertyValue: string
    },
  ) {
    const state = ensureRelationshipState(key)
    state.searchProperty = params.propertyName
    state.searchValue = params.propertyValue
    state.activeSearch = true
    const result = await fetchRelationshipInstances(key, {
      relationshipType: params.relationshipType,
      sourceEntityType: params.sourceEntityType,
      targetEntityType: params.targetEntityType,
      offset: 0,
      propertyName: params.propertyName,
      propertyValue: params.propertyValue,
    })
    state.instances = result.instances
    state.total = result.total
  }

  async function clearRelationshipSearch(
    key: string,
    params: {
      relationshipType: string
      sourceEntityType: string
      targetEntityType: string
      seedInstances: DesignArtifactInstance[]
      total: number
    },
  ) {
    const state = ensureRelationshipState(key)
    state.searchProperty = ''
    state.searchValue = ''
    state.activeSearch = false
    state.instances = [...params.seedInstances]
    state.total = params.total
  }

  async function loadMoreRelationshipInstances(
    key: string,
    params: {
      relationshipType: string
      sourceEntityType: string
      targetEntityType: string
    },
  ) {
    const state = ensureRelationshipState(key)
    const result = await fetchRelationshipInstances(key, {
      relationshipType: params.relationshipType,
      sourceEntityType: params.sourceEntityType,
      targetEntityType: params.targetEntityType,
      offset: state.instances.length,
      propertyName: state.activeSearch ? state.searchProperty : undefined,
      propertyValue: state.activeSearch ? state.searchValue : undefined,
    })
    state.instances = [...state.instances, ...result.instances]
    state.total = result.total
  }

  return {
    entityStates,
    relationshipStates,
    ensureEntityState,
    ensureRelationshipState,
    searchEntityInstances,
    clearEntitySearch,
    loadMoreEntityInstances,
    searchRelationshipInstances,
    clearRelationshipSearch,
    loadMoreRelationshipInstances,
  }
}
