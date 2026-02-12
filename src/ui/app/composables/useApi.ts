/**
 * Convenience composable that aggregates all bounded-context API modules
 * into a single entry point.
 *
 * Usage:
 *   const { iam, graph, query } = useApi()
 *   const tenants = await iam.listTenants()
 */
export function useApi() {
  return {
    iam: useIamApi(),
    graph: useGraphApi(),
    query: useQueryApi(),
  }
}
