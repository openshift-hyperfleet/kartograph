# Changelog

## [3.5.0](https://github.com/openshift-hyperfleet/kartograph/compare/v3.4.0...v3.5.0) (2026-02-03)


### Features

* **api.query:** support github/lab token via MCP header ([#181](https://github.com/openshift-hyperfleet/kartograph/issues/181)) ([d754062](https://github.com/openshift-hyperfleet/kartograph/commit/d75406249d40db2786e595f2f1c934c72ac37335))

## [3.4.0](https://github.com/openshift-hyperfleet/kartograph/compare/v3.3.0...v3.4.0) (2026-02-03)


### Features

* **query:** add agent instructions MCP resource ([#159](https://github.com/openshift-hyperfleet/kartograph/issues/159)) ([05a8540](https://github.com/openshift-hyperfleet/kartograph/commit/05a85407cd4aa50f00a4c26ae429d7fa1a025f1d))

## [3.3.0](https://github.com/openshift-hyperfleet/kartograph/compare/v3.2.0...v3.3.0) (2026-01-30)


### Features

* **api.iam:** persist tenant membership ([#178](https://github.com/openshift-hyperfleet/kartograph/issues/178)) ([37fb14c](https://github.com/openshift-hyperfleet/kartograph/commit/37fb14c8400d419dad4d69461c62d3e0a970f454))

## [3.2.0](https://github.com/openshift-hyperfleet/kartograph/compare/v3.1.5...v3.2.0) (2026-01-29)


### Features

* **api.iam:** tenant membership foundation ([#176](https://github.com/openshift-hyperfleet/kartograph/issues/176)) ([07a6389](https://github.com/openshift-hyperfleet/kartograph/commit/07a638918d516f40b41fb96179b42f47e3efbcd0))

## [3.1.5](https://github.com/openshift-hyperfleet/kartograph/compare/v3.1.4...v3.1.5) (2026-01-27)


### Bug Fixes

* **build:** rbac labels ([#167](https://github.com/openshift-hyperfleet/kartograph/issues/167)) ([a91e5f1](https://github.com/openshift-hyperfleet/kartograph/commit/a91e5f10c6ee3505f795401fc126633af2400c7f))
* **deploy:** add init waiter SA to kustomization ([#171](https://github.com/openshift-hyperfleet/kartograph/issues/171)) ([795dfa0](https://github.com/openshift-hyperfleet/kartograph/commit/795dfa0fae2e91c584a75fe552a179d018524c08))
* **deploy:** remove selectors from jobs ([#170](https://github.com/openshift-hyperfleet/kartograph/issues/170)) ([72e0312](https://github.com/openshift-hyperfleet/kartograph/commit/72e031254c916d2072d6a1fe6bce42e0ed82ec0e))
* **deploy:** update sha references ([#172](https://github.com/openshift-hyperfleet/kartograph/issues/172)) ([56f7f52](https://github.com/openshift-hyperfleet/kartograph/commit/56f7f5242897cdf5abcdf949789bf5ca54d2acbc))

## [3.1.4](https://github.com/openshift-hyperfleet/kartograph/compare/v3.1.3...v3.1.4) (2026-01-27)


### Bug Fixes

* **build:** add argocd job replace annotation ([#163](https://github.com/openshift-hyperfleet/kartograph/issues/163)) ([0c13298](https://github.com/openshift-hyperfleet/kartograph/commit/0c13298262f35db7703cb39306877ee23c167ed5))
* **build:** replace wait for in jobs and rbac account labels ([#166](https://github.com/openshift-hyperfleet/kartograph/issues/166)) ([96d8f4a](https://github.com/openshift-hyperfleet/kartograph/commit/96d8f4aa73529b19d7d2a84cf30e9e66ee88be87))


### Documentation

* add Star History section to README ([#165](https://github.com/openshift-hyperfleet/kartograph/issues/165)) ([5a3b372](https://github.com/openshift-hyperfleet/kartograph/commit/5a3b3723590139648d054214a92d1f6eb9d6be1c))

## [3.1.3](https://github.com/openshift-hyperfleet/kartograph/compare/v3.1.2...v3.1.3) (2026-01-27)


### Bug Fixes

* **deploy:** fix k8s wait for image ([#158](https://github.com/openshift-hyperfleet/kartograph/issues/158)) ([6f6e79f](https://github.com/openshift-hyperfleet/kartograph/commit/6f6e79fc441dade6ed990659623df5200393d396))

## [3.1.2](https://github.com/openshift-hyperfleet/kartograph/compare/v3.1.1...v3.1.2) (2026-01-27)


### Bug Fixes

* **deploy:** fix spicedb and postgres sec contexts ([#156](https://github.com/openshift-hyperfleet/kartograph/issues/156)) ([d177ce0](https://github.com/openshift-hyperfleet/kartograph/commit/d177ce0ae3a1089a571932e169837e368f37bf54))

## [3.1.1](https://github.com/openshift-hyperfleet/kartograph/compare/v3.1.0...v3.1.1) (2026-01-27)


### Bug Fixes

* **build:** update stage uid/gids ([#154](https://github.com/openshift-hyperfleet/kartograph/issues/154)) ([3ad3f24](https://github.com/openshift-hyperfleet/kartograph/commit/3ad3f245e81b6e3aa029d42d7f026501882004f0))

## [3.1.0](https://github.com/openshift-hyperfleet/kartograph/compare/v3.0.0...v3.1.0) (2026-01-27)


### Features

* data loading script ([#152](https://github.com/openshift-hyperfleet/kartograph/issues/152)) ([f5256b6](https://github.com/openshift-hyperfleet/kartograph/commit/f5256b6a4c02103fa902416b033691b5398e2c78))

## [3.0.0](https://github.com/openshift-hyperfleet/kartograph/compare/v2.1.0...v3.0.0) (2026-01-26)


### ⚠ BREAKING CHANGES

* **api.iam:** basic API key support ([#148](https://github.com/openshift-hyperfleet/kartograph/issues/148))

### Features

* **api.iam:** basic API key support ([#148](https://github.com/openshift-hyperfleet/kartograph/issues/148)) ([7f90502](https://github.com/openshift-hyperfleet/kartograph/commit/7f9050267268fbaa3c4f821773ce2b756e085560))

## [2.1.0](https://github.com/openshift-hyperfleet/kartograph/compare/v2.0.0...v2.1.0) (2026-01-21)


### Features

* enforce authentication on protected endpoints ([#144](https://github.com/openshift-hyperfleet/kartograph/issues/144)) ([2ef51b6](https://github.com/openshift-hyperfleet/kartograph/commit/2ef51b63ddecdea77077f0f226d52e9564519427))

## [2.0.0](https://github.com/openshift-hyperfleet/kartograph/compare/v1.2.0...v2.0.0) (2026-01-21)


### ⚠ BREAKING CHANGES

* add OIDC authentication support ([#141](https://github.com/openshift-hyperfleet/kartograph/issues/141))

### Features

* add OIDC authentication support ([#141](https://github.com/openshift-hyperfleet/kartograph/issues/141)) ([a34d349](https://github.com/openshift-hyperfleet/kartograph/commit/a34d3492f160a54a73e67287e2af74f6f369176a))

## [1.2.0](https://github.com/openshift-hyperfleet/kartograph/compare/v1.1.7...v1.2.0) (2026-01-20)


### Features

* **api.iam:** add tenant aggregate object ([#139](https://github.com/openshift-hyperfleet/kartograph/issues/139)) ([cf23207](https://github.com/openshift-hyperfleet/kartograph/commit/cf232076a40b8c2e34219ab43270e4ddde562622))

## [1.1.7](https://github.com/openshift-hyperfleet/kartograph/compare/v1.1.6...v1.1.7) (2026-01-19)


### Documentation

* document bulk loading ([#137](https://github.com/openshift-hyperfleet/kartograph/issues/137)) ([b3c2c23](https://github.com/openshift-hyperfleet/kartograph/commit/b3c2c23bbc1b79119b5e419fae94a7bdbf325ca1))

## [1.1.6](https://github.com/openshift-hyperfleet/kartograph/compare/v1.1.5...v1.1.6) (2026-01-16)


### Bug Fixes

* **ci:** always build on main ([#128](https://github.com/openshift-hyperfleet/kartograph/issues/128)) ([fbfc492](https://github.com/openshift-hyperfleet/kartograph/commit/fbfc4929a86a6f0c2cd4c0b6f0215798f7a11501))

## [1.1.5](https://github.com/openshift-hyperfleet/kartograph/compare/v1.1.4...v1.1.5) (2026-01-16)


### Documentation

* add architecture overview and typical user journey ([#126](https://github.com/openshift-hyperfleet/kartograph/issues/126)) ([9a0dd6d](https://github.com/openshift-hyperfleet/kartograph/commit/9a0dd6da88ad16d42bddb802a0f86ee5de40bc7a))

## [1.1.4](https://github.com/openshift-hyperfleet/kartograph/compare/v1.1.3...v1.1.4) (2026-01-16)


### Bug Fixes

* **ci:** add staging namespace for management with argocd ([#124](https://github.com/openshift-hyperfleet/kartograph/issues/124)) ([f95ab1b](https://github.com/openshift-hyperfleet/kartograph/commit/f95ab1be3e7494c53027333a548d605f17cef45d))

## [1.1.3](https://github.com/openshift-hyperfleet/kartograph/compare/v1.1.2...v1.1.3) (2026-01-16)


### Bug Fixes

* **ci:** update repoURL for kartograph-stage deployment ([#121](https://github.com/openshift-hyperfleet/kartograph/issues/121)) ([9494315](https://github.com/openshift-hyperfleet/kartograph/commit/94943152b6d4b6cbb4d5342134e82ba0f6fae577))

## [1.1.2](https://github.com/openshift-hyperfleet/kartograph/compare/v1.1.1...v1.1.2) (2026-01-16)


### Bug Fixes

* Update contributing section in README ([#119](https://github.com/openshift-hyperfleet/kartograph/issues/119)) ([60878c8](https://github.com/openshift-hyperfleet/kartograph/commit/60878c8d852b346c8b13cd92013e4147d77c353d))

## [1.1.1](https://github.com/openshift-hyperfleet/kartograph/compare/v1.1.0...v1.1.1) (2026-01-16)


### Bug Fixes

* **deps:** update dependency fastmcp to v2.14.3 ([#107](https://github.com/openshift-hyperfleet/kartograph/issues/107)) ([691fafe](https://github.com/openshift-hyperfleet/kartograph/commit/691fafe7665c2e63ccf8380df5342b19df8a1dcf))

## [1.1.0](https://github.com/openshift-hyperfleet/kartograph/compare/v1.0.0...v1.1.0) (2026-01-16)


### Features

* **build:** add initial k8s manifests ([#113](https://github.com/openshift-hyperfleet/kartograph/issues/113)) ([022cf65](https://github.com/openshift-hyperfleet/kartograph/commit/022cf6553b90bd4d8a3d09107eaebe7403b0e479))

## [1.0.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.17.1...v1.0.0) (2026-01-15)


### ⚠ BREAKING CHANGES

* **api.infrastructure:** OutboxWorker.__init__ signature changed - db_url replaced with event_source parameter.

### Code Refactoring

* **api.infrastructure:** refactor outbox worker to use pluggable event source ([#111](https://github.com/openshift-hyperfleet/kartograph/issues/111)) ([de6cdbc](https://github.com/openshift-hyperfleet/kartograph/commit/de6cdbc6817fa036427e667f73b705fff5c673d6))

## [0.17.1](https://github.com/openshift-hyperfleet/kartograph/compare/v0.17.0...v0.17.1) (2026-01-14)


### Documentation

* refine documentation ([#109](https://github.com/openshift-hyperfleet/kartograph/issues/109)) ([0a614cc](https://github.com/openshift-hyperfleet/kartograph/commit/0a614cc04e93606147ed1a83add5f260508ccdff))

## [0.17.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.16.0...v0.17.0) (2026-01-14)


### Features

* **outbox:** implement transactional outbox pattern for SpiceDB consistency ([#106](https://github.com/openshift-hyperfleet/kartograph/issues/106)) ([98024df](https://github.com/openshift-hyperfleet/kartograph/commit/98024df027971e37f73a1846bef75af55bb9f11c))

## [0.16.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.15.0...v0.16.0) (2026-01-08)


### Features

* **iam:** add IAM FastAPI endpoints with integration tests ([#103](https://github.com/openshift-hyperfleet/kartograph/issues/103)) ([ffadff4](https://github.com/openshift-hyperfleet/kartograph/commit/ffadff466dc6a9b3608d3bc137baf33265b8a603))

## [0.15.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.14.0...v0.15.0) (2026-01-06)


### Features

* **iam:** implement application service layer ([#99](https://github.com/openshift-hyperfleet/kartograph/issues/99)) ([a3d4b7b](https://github.com/openshift-hyperfleet/kartograph/commit/a3d4b7b5c0c74d3a8097d89b3ed6277353fef257))

## [0.14.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.13.2...v0.14.0) (2026-01-06)


### Features

* **iam:** implement repository layer ([#95](https://github.com/openshift-hyperfleet/kartograph/issues/95)) ([49a89d8](https://github.com/openshift-hyperfleet/kartograph/commit/49a89d82ac131e45a473e3d244eaeebc014a7236))

## [0.13.2](https://github.com/openshift-hyperfleet/kartograph/compare/v0.13.1...v0.13.2) (2026-01-05)


### Bug Fixes

* **api.shared_kernel:** use async SpiceDB client ([#92](https://github.com/openshift-hyperfleet/kartograph/issues/92)) ([bac441e](https://github.com/openshift-hyperfleet/kartograph/commit/bac441ebee51da1a218589c3044917a7e5e4aee8))

## [0.13.1](https://github.com/openshift-hyperfleet/kartograph/compare/v0.13.0...v0.13.1) (2026-01-05)


### Bug Fixes

* **deps:** update dependency fastmcp to v2.14.2 ([#90](https://github.com/openshift-hyperfleet/kartograph/issues/90)) ([5317dd8](https://github.com/openshift-hyperfleet/kartograph/commit/5317dd8875eec132fc9a1615e8b2194d420d4b2c))

## [0.13.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.12.0...v0.13.0) (2025-12-23)


### Features

* **iam:** IAM domain models and business logic ([#86](https://github.com/openshift-hyperfleet/kartograph/issues/86)) ([0adb133](https://github.com/openshift-hyperfleet/kartograph/commit/0adb133efbb075bf5a150f294d29c2e363b69d47))

## [0.12.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.11.0...v0.12.0) (2025-12-23)


### Features

* **api:** database foundation with SQLAlchemy and Alembic ([#84](https://github.com/openshift-hyperfleet/kartograph/issues/84)) ([9327b82](https://github.com/openshift-hyperfleet/kartograph/commit/9327b82eab2fd98b6cec2c90af708b428fe3b56a))

## [0.11.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.10.1...v0.11.0) (2025-12-23)


### Features

* **api:** authorization abstractions and SpiceDB client ([#85](https://github.com/openshift-hyperfleet/kartograph/issues/85)) ([8fc16b5](https://github.com/openshift-hyperfleet/kartograph/commit/8fc16b5346f68f14fd1f0c2676345eb455f13d66))

## [0.10.1](https://github.com/openshift-hyperfleet/kartograph/compare/v0.10.0...v0.10.1) (2025-12-22)


### Documentation

* add readme banner ([#82](https://github.com/openshift-hyperfleet/kartograph/issues/82)) ([ccaa5f3](https://github.com/openshift-hyperfleet/kartograph/commit/ccaa5f3bdb91a3b4ae0ef05321570e6ba6eecf96))

## [0.10.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.9.2...v0.10.0) (2025-12-22)


### Features

* **graph:** enable schema learning for UPDATE operations ([#79](https://github.com/openshift-hyperfleet/kartograph/issues/79)) ([8fdbdc5](https://github.com/openshift-hyperfleet/kartograph/commit/8fdbdc536a64a33d5c40b1b661b1d4d83a521a38))
* **shared-kernel:** add edge ID generation with tenant_id support ([#78](https://github.com/openshift-hyperfleet/kartograph/issues/78)) ([3135935](https://github.com/openshift-hyperfleet/kartograph/commit/31359355269ef4759f54eff30a5133eae97702d6))

## [0.9.2](https://github.com/openshift-hyperfleet/kartograph/compare/v0.9.1...v0.9.2) (2025-12-22)


### Bug Fixes

* **graph:** support edge DELETE and UPDATE operations ([#77](https://github.com/openshift-hyperfleet/kartograph/issues/77)) ([28a5a24](https://github.com/openshift-hyperfleet/kartograph/commit/28a5a24752e50351981606068f1757edcb915e95))

## [0.9.1](https://github.com/openshift-hyperfleet/kartograph/compare/v0.9.0...v0.9.1) (2025-12-19)


### Documentation

* **website:** add MCP server guide and fix all internal links ([#69](https://github.com/openshift-hyperfleet/kartograph/issues/69)) ([354d40a](https://github.com/openshift-hyperfleet/kartograph/commit/354d40a161241e3c7a17a9e9ea330215936231db))

## [0.9.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.8.0...v0.9.0) (2025-12-19)


### Features

* **api.query:** add schema discovery MCP resources ([#67](https://github.com/openshift-hyperfleet/kartograph/issues/67)) ([cf90067](https://github.com/openshift-hyperfleet/kartograph/commit/cf90067c03f0d300cc9012914ffff16dd4dc478c))

## [0.8.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.7.0...v0.8.0) (2025-12-19)


### Features

* **api:** add shared kernel with EntityIdGenerator for cross-context ID consistency ([#65](https://github.com/openshift-hyperfleet/kartograph/issues/65)) ([6f039cd](https://github.com/openshift-hyperfleet/kartograph/commit/6f039cd85163fbbb4e1b356f0969c333c483c946))

## [0.7.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.6.0...v0.7.0) (2025-12-18)


### Features

* **api.graph:** add ontology endpoints ([#61](https://github.com/openshift-hyperfleet/kartograph/issues/61)) ([72e0eb4](https://github.com/openshift-hyperfleet/kartograph/commit/72e0eb42e56690221a00f8297f16a3d879532689))

## [0.6.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.5.0...v0.6.0) (2025-12-17)


### Features

* add ThreadedConnectionPool for thread-safe database access ([#59](https://github.com/openshift-hyperfleet/kartograph/issues/59)) ([7c55483](https://github.com/openshift-hyperfleet/kartograph/commit/7c554834debf3a46a1333d52bdec3edb0cd750cd))

## [0.5.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.4.1...v0.5.0) (2025-12-17)


### Features

* add MCP Cypher query tool (tracer bullet) ([#57](https://github.com/openshift-hyperfleet/kartograph/issues/57)) ([04556ad](https://github.com/openshift-hyperfleet/kartograph/commit/04556adc9790dc4a0bf507d5946dd835cd44ce93))

## [0.4.1](https://github.com/openshift-hyperfleet/kartograph/compare/v0.4.0...v0.4.1) (2025-12-16)


### Bug Fixes

* **deps:** update astro monorepo ([#53](https://github.com/openshift-hyperfleet/kartograph/issues/53)) ([651e2ed](https://github.com/openshift-hyperfleet/kartograph/commit/651e2ed232395ef4b78e36545fd462f113dc404a))

## [0.4.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.3.1...v0.4.0) (2025-12-16)


### Features

* **website:** add edit links and customize footer ([#54](https://github.com/openshift-hyperfleet/kartograph/issues/54)) ([ee4b8ab](https://github.com/openshift-hyperfleet/kartograph/commit/ee4b8ab09191c9fa4fdce0572f8946a876b5777f))

## [0.3.1](https://github.com/openshift-hyperfleet/kartograph/compare/v0.3.0...v0.3.1) (2025-12-15)


### Documentation

* add app version and last edit timestamp ([#49](https://github.com/openshift-hyperfleet/kartograph/issues/49)) ([8cf2002](https://github.com/openshift-hyperfleet/kartograph/commit/8cf20027fc275b2854fe7e6e112de47f4085de3b))

## [0.3.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.2.5...v0.3.0) (2025-12-15)


### Features

* **api.query:** implement hello-world mcp server ([#47](https://github.com/openshift-hyperfleet/kartograph/issues/47)) ([bd6fc79](https://github.com/openshift-hyperfleet/kartograph/commit/bd6fc7934f9ff11ba2ab7287b154d9ceff7e3448))

## [0.2.5](https://github.com/openshift-hyperfleet/kartograph/compare/v0.2.4...v0.2.5) (2025-12-15)


### Bug Fixes

* **tests:** update protocol mocks to return NodeNeighborsResult ([#45](https://github.com/openshift-hyperfleet/kartograph/issues/45)) ([aad481d](https://github.com/openshift-hyperfleet/kartograph/commit/aad481de92955b12c8ab97be66977d55cfe750d2))

## [0.2.4](https://github.com/openshift-hyperfleet/kartograph/compare/v0.2.3...v0.2.4) (2025-12-15)


### Documentation

* fix documentation link in README ([#41](https://github.com/openshift-hyperfleet/kartograph/issues/41)) ([7de5bce](https://github.com/openshift-hyperfleet/kartograph/commit/7de5bcea92f935ea70a25ca79774d424bff33392))

## [0.2.3](https://github.com/openshift-hyperfleet/kartograph/compare/v0.2.2...v0.2.3) (2025-12-12)


### Bug Fixes

* **docs:** hotfix quickstart link ([25044e9](https://github.com/openshift-hyperfleet/kartograph/commit/25044e97d5ee31ad5839a76226b0224af4623487))


### Documentation

* add documentation link to README ([#35](https://github.com/openshift-hyperfleet/kartograph/issues/35)) ([775a294](https://github.com/openshift-hyperfleet/kartograph/commit/775a2943f7e6137c27aade46310ff40d84f898fe))

## [0.2.2](https://github.com/openshift-hyperfleet/kartograph/compare/v0.2.1...v0.2.2) (2025-12-12)


### Bug Fixes

* **api.graph:** Resolve CREATE operation failures in mutation applier ([#31](https://github.com/openshift-hyperfleet/kartograph/issues/31)) ([e114518](https://github.com/openshift-hyperfleet/kartograph/commit/e114518039938b9a8dbc7fa475ac9c8be90bf7ac))


### Documentation

* Add link to JSON schema viewer. ([#32](https://github.com/openshift-hyperfleet/kartograph/issues/32)) ([0958bdf](https://github.com/openshift-hyperfleet/kartograph/commit/0958bdf21936589a3cf2768edc9b2e4a8bc17aa8))

## [0.2.1](https://github.com/openshift-hyperfleet/kartograph/compare/v0.2.0...v0.2.1) (2025-12-12)


### Bug Fixes

* **ci:** Parse JSON output from release-please v4 action ([#29](https://github.com/openshift-hyperfleet/kartograph/issues/29)) ([41e448c](https://github.com/openshift-hyperfleet/kartograph/commit/41e448c5cdadab5ea6e025275c2f96190838ad5d))


### Documentation

* Don't put behind /kartograph by default ([b7bb54b](https://github.com/openshift-hyperfleet/kartograph/commit/b7bb54b306b0c974978583a612ba822e37561c0c))

## [0.2.0](https://github.com/openshift-hyperfleet/kartograph/compare/v0.1.3...v0.2.0) (2025-12-09)


### Features

* **graph:** Add database connection layer for Apache AGE ([#14](https://github.com/openshift-hyperfleet/kartograph/issues/14)) ([09070e2](https://github.com/openshift-hyperfleet/kartograph/commit/09070e2d991de5c86c72c4bd586d01a6eeb7a7b3))

## [0.1.3](https://github.com/openshift-hyperfleet/kartograph/compare/v0.1.2...v0.1.3) (2025-12-08)


### Documentation

* Update README with image source links ([#12](https://github.com/openshift-hyperfleet/kartograph/issues/12)) ([c599e8d](https://github.com/openshift-hyperfleet/kartograph/commit/c599e8db4f850545e2cf82ee0fd9f9c7d3ce7212))

## [0.1.2](https://github.com/openshift-hyperfleet/kartograph/compare/v0.1.1...v0.1.2) (2025-12-08)


### Bug Fixes

* Correct auto-merge command in release-please workflow ([a35b081](https://github.com/openshift-hyperfleet/kartograph/commit/a35b0812866341e0a789d8eec9e54521dd766693))
* Extract PR number from JSON object in release-please ([5ad7e9d](https://github.com/openshift-hyperfleet/kartograph/commit/5ad7e9df7a342e549dea78bb3dbf9ffc0d0f33aa))
* Only run auto-merge when PR is created ([dca6a9a](https://github.com/openshift-hyperfleet/kartograph/commit/dca6a9a3dcbb850f22f432e5b6bfd2be34d1aa2d))


### Documentation

* Add pre-commit install instructions ([588c933](https://github.com/openshift-hyperfleet/kartograph/commit/588c933d9f8dd1f4cc9af195eba3f5d354c61733))
* Flesh out AGENTS.md ([c3f017e](https://github.com/openshift-hyperfleet/kartograph/commit/c3f017e30ce7d47951bae18aea6b24e71f189d4c))

## [0.1.1](https://github.com/openshift-hyperfleet/kartograph/compare/kartograph-v0.1.0...kartograph-v0.1.1) (2025-12-08)


### Bug Fixes

* Correct auto-merge command in release-please workflow ([a35b081](https://github.com/openshift-hyperfleet/kartograph/commit/a35b0812866341e0a789d8eec9e54521dd766693))
* Extract PR number from JSON object in release-please ([5ad7e9d](https://github.com/openshift-hyperfleet/kartograph/commit/5ad7e9df7a342e549dea78bb3dbf9ffc0d0f33aa))


### Documentation

* Add pre-commit install instructions ([588c933](https://github.com/openshift-hyperfleet/kartograph/commit/588c933d9f8dd1f4cc9af195eba3f5d354c61733))
* Flesh out AGENTS.md ([c3f017e](https://github.com/openshift-hyperfleet/kartograph/commit/c3f017e30ce7d47951bae18aea6b24e71f189d4c))

## 0.1.0 (2025-12-05)


### Features

* initial release with Docker support and basic FastAPI setup
