targetScope = 'resourceGroup'

metadata description = 'Deploy the Foundry workshop into the dedicated resource group already created in Azure Portal.'

@description('Workshop resource location. Japan East only; the existing resource group metadata location does not override this value.')
@allowed([
  'japaneast'
])
param location string = 'japaneast'

@description('Administrator-verified gpt-5.6-luna version available with GlobalStandard in Japan East. No version is guessed.')
@minLength(1)
@maxLength(64)
param primaryModelVersion string

@description('Administrator-verified gpt-5.5 version available with GlobalStandard in Japan East. No version is guessed.')
@minLength(1)
@maxLength(64)
param evaluationModelVersion string

@description('Administrator-verified text-embedding-3-small version available with GlobalStandard in Japan East.')
@minLength(1)
@maxLength(64)
param embeddingModelVersion string

@description('Public GHCR Travel Ops API image: ghcr.io/<owner>/<image>@sha256:<64 lowercase hexadecimal characters>. Tags and private registry credentials are not accepted.')
@minLength(83)
@maxLength(256)
param travelApiImageRef string

@description('Published lowercase 40-character commit SHA in matayuuu/Microsoft-Foundry-Agent-Service-Handson. Used for bootstrap source, citations, and the handoff manifest.')
@minLength(40)
@maxLength(40)
param sourceRevision string

@description('Intended participant Entra User object ID. Leave empty only when the participant deploys personally. Specify the same participant for administrator/automation redeployment.')
@maxLength(36)
param participantObjectIdOverride string = ''

@description('Stable bootstrap rerun identifier. Keep unchanged for normal redeployment; change deliberately to repeat initialization. It does not change resource names.')
@minLength(1)
@maxLength(64)
param bootstrapRunId string = '1'

// ARM parameters have no regex constraint. Reject invalid immutable inputs before
// they can be used as an image or source URL; fail() never supplies a fallback.
var sourceRevisionIsImmutable = length(sourceRevision) == 40 && empty(filter(
  range(0, length(sourceRevision)),
  index => !contains('0123456789abcdef', substring(sourceRevision, index, 1))
))
var validatedSourceRevision = sourceRevisionIsImmutable
  ? sourceRevision
  : fail('sourceRevision must be a published lowercase 40-character hexadecimal commit SHA.')

var imageParts = split(travelApiImageRef, '@sha256:')
var imageRepository = first(imageParts)
var imageDigest = last(imageParts)
var imagePathSegments = split(imageRepository, '/')
var imagePathIsValid = length(imagePathSegments) >= 3 && !contains(imagePathSegments, '') && !contains(
  imagePathSegments,
  '.'
) && !contains(imagePathSegments, '..')
var imageRepositoryIsValid = startsWith(imageRepository, 'ghcr.io/') && imagePathIsValid && empty(filter(
  range(0, length(imageRepository)),
  index => !contains('abcdefghijklmnopqrstuvwxyz0123456789._/-', substring(imageRepository, index, 1))
))
var imageDigestIsValid = length(imageDigest) == 64 && empty(filter(
  range(0, length(imageDigest)),
  index => !contains('0123456789abcdef', substring(imageDigest, index, 1))
))
var imageReferenceIsImmutable = length(imageParts) == 2 && imageRepositoryIsValid && imageDigestIsValid
var validatedTravelApiImageRef = imageReferenceIsImmutable
  ? travelApiImageRef
  : fail('travelApiImageRef must be a public ghcr.io/<owner>/<image>@sha256:<64 lowercase hexadecimal characters> reference without a tag.')

// Resolve the deployer only at this root boundary, never inside the script.
var participantObjectId = toLower(empty(participantObjectIdOverride) ? deployer().objectId : participantObjectIdOverride)
var sourceBase = 'https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/${validatedSourceRevision}'
var nameSuffix = uniqueString(resourceGroup().id, location)
var names = {
  foundry: 'aif-fdyws-${nameSuffix}'
  project: 'contoso-travel'
  search: 'srch-fdyws-${nameSuffix}'
  logAnalytics: 'log-fdyws-${nameSuffix}'
  appInsights: 'appi-fdyws-${nameSuffix}'
  containerEnvironment: 'cae-fdyws-${nameSuffix}'
  travelApi: 'ca-travel-api-${nameSuffix}'
  azureml: 'mlw-fdyws-${nameSuffix}'
  storage: 'stfdyws${nameSuffix}'
  keyVault: 'kv-fdyws-${nameSuffix}'
  bootstrapIdentity: 'id-fdyws-bootstrap-${nameSuffix}'
  bootstrap: 'ds-fdyws-bootstrap-${nameSuffix}'
}
var connectionNames = {
  search: 'contoso-travel-search'
  knowledgeMcp: 'contoso-travel-knowledge-lab-mcp'
  appInsights: 'contoso-travel-appinsights'
}
var tags = {
  workshop: 'foundry-agent-service-handson'
  'managed-by': 'bicep'
  'source-revision': validatedSourceRevision
}
var roleIds = {
  foundryUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
  foundryProjectManager: 'eadc314b-1a2d-4efa-be10-5d325db5065e'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  logAnalyticsReader: '73c42c96-874c-492b-b04d-ab87d138a893'
  privilegedMonitoringDataReader: 'dbc9c667-e97f-4491-aee6-90b9cf960190'
  monitoringMetricsPublisher: '3913510d-42f4-4e42-8a64-420c390055eb'
  cognitiveServicesOpenAIUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  azuremlDataScientist: 'f6c7c914-8db3-469d-8ca1-694a8f32e121'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  keyVaultSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  reader: 'acdd72a7-3385-48ef-bd42-f606fba81ae7'
}

resource foundry 'Microsoft.CognitiveServices/accounts@2026-05-01' = {
  name: names.foundry
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: names.foundry
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2026-05-01' = {
  parent: foundry
  name: names.project
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Contoso Travel & Expense Workshop'
    description: 'Basic Agent Setup project for the Foundry Agent Service hands-on workshop.'
  }
}

// Serialize child PUTs: a fresh Foundry account rejects concurrent model writes.
resource primaryModel 'Microsoft.CognitiveServices/accounts/deployments@2026-05-01' = {
  parent: foundry
  name: 'gpt-5.6-luna'
  sku: {
    name: 'GlobalStandard'
    capacity: 40
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5.6-luna'
      version: primaryModelVersion
    }
  }
  dependsOn: [
    project
  ]
}

resource evaluationModel 'Microsoft.CognitiveServices/accounts/deployments@2026-05-01' = {
  parent: foundry
  name: 'gpt-5.5'
  sku: {
    name: 'GlobalStandard'
    capacity: 100
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5.5'
      version: evaluationModelVersion
    }
  }
  dependsOn: [
    primaryModel
  ]
}

resource embeddingModel 'Microsoft.CognitiveServices/accounts/deployments@2026-05-01' = {
  parent: foundry
  name: 'embedding'
  sku: {
    name: 'GlobalStandard'
    capacity: 40
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: embeddingModelVersion
    }
  }
  dependsOn: [
    evaluationModel
  ]
}

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: names.search
  location: location
  tags: tags
  sku: {
    name: 'basic'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    partitionCount: 1
    replicaCount: 1
    semanticSearch: 'free'
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: names.logAnalytics
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: names.appInsights
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    DisableLocalAuth: true
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource containerEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: names.containerEnvironment
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource travelApi 'Microsoft.App/containerApps@2025-01-01' = {
  name: names.travelApi
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
    }
    template: {
      containers: [
        {
          name: 'travel-api'
          image: validatedTravelApiImageRef
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'WORKSHOP_SOURCE_BASE'
              value: sourceBase
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: names.storage
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    // AML's default datastore still requires Shared Key compatibility.
    allowSharedKeyAccess: true
    allowBlobPublicAccess: false
    defaultToOAuthAuthentication: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' = {
  parent: storage
  name: 'default'
}

resource artifactContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = {
  parent: blobService
  name: 'workshop-files'
  properties: {
    publicAccess: 'None'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: names.keyVault
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    accessPolicies: []
    publicNetworkAccess: 'Enabled'
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    // Omit purge protection; the service rejects an explicit false value.
  }
}

resource azureml 'Microsoft.MachineLearningServices/workspaces@2025-06-01' = {
  name: names.azureml
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    applicationInsights: appInsights.id
    keyVault: keyVault.id
    storageAccount: storage.id
    publicNetworkAccess: 'Enabled'
    hbiWorkspace: false
    v1LegacyMode: false
  }
}

resource bootstrapIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: names.bootstrapIdentity
  location: location
  tags: tags
}

resource participantFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, participantObjectId, roleIds.foundryUser)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.foundryUser)
    principalId: participantObjectId
    principalType: 'User'
  }
}

resource participantProjectManager 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, participantObjectId, roleIds.foundryProjectManager)
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.foundryProjectManager)
    principalId: participantObjectId
    principalType: 'User'
  }
}

resource participantSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, participantObjectId, roleIds.searchServiceContributor)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.searchServiceContributor
    )
    principalId: participantObjectId
    principalType: 'User'
  }
}

resource participantSearchIndexDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, participantObjectId, roleIds.searchIndexDataContributor)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.searchIndexDataContributor
    )
    principalId: participantObjectId
    principalType: 'User'
  }
}

resource participantLogAnalyticsReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logAnalytics.id, participantObjectId, roleIds.logAnalyticsReader)
  scope: logAnalytics
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.logAnalyticsReader)
    principalId: participantObjectId
    principalType: 'User'
  }
}

resource participantMonitoringDataReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appInsights.id, participantObjectId, roleIds.privilegedMonitoringDataReader)
  scope: appInsights
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.privilegedMonitoringDataReader
    )
    principalId: participantObjectId
    principalType: 'User'
  }
}

resource participantAzuremlDataScientist 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(azureml.id, participantObjectId, roleIds.azuremlDataScientist)
  scope: azureml
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.azuremlDataScientist)
    principalId: participantObjectId
    principalType: 'User'
  }
}

resource participantStorageBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, participantObjectId, roleIds.storageBlobDataContributor)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.storageBlobDataContributor
    )
    principalId: participantObjectId
    principalType: 'User'
  }
}

// AML automatically assigns its workspace identity Storage Blob Data Contributor.
// Declaring that same grant races the platform and causes RoleAssignmentExists.
resource azuremlKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, azureml.id, roleIds.keyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.keyVaultSecretsUser)
    principalId: azureml.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, project.id, roleIds.foundryUser)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.foundryUser)
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectSearchIndexDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, project.id, roleIds.searchIndexDataContributor)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.searchIndexDataContributor
    )
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, project.id, roleIds.searchServiceContributor)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.searchServiceContributor
    )
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectMonitoringMetricsPublisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appInsights.id, project.id, roleIds.monitoringMetricsPublisher)
  scope: appInsights
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.monitoringMetricsPublisher
    )
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectLogAnalyticsReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appInsights.id, project.id, roleIds.logAnalyticsReader)
  scope: appInsights
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.logAnalyticsReader)
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectMonitoringDataReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appInsights.id, project.id, roleIds.privilegedMonitoringDataReader)
  scope: appInsights
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.privilegedMonitoringDataReader
    )
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource searchOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, search.id, roleIds.cognitiveServicesOpenAIUser)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.cognitiveServicesOpenAIUser
    )
    principalId: search.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource bootstrapFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, bootstrapIdentity.id, roleIds.foundryUser)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.foundryUser)
    principalId: bootstrapIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource bootstrapSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, bootstrapIdentity.id, roleIds.searchServiceContributor)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.searchServiceContributor
    )
    principalId: bootstrapIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource bootstrapSearchIndexDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, bootstrapIdentity.id, roleIds.searchIndexDataContributor)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.searchIndexDataContributor
    )
    principalId: bootstrapIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource bootstrapReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, bootstrapIdentity.id, roleIds.reader)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.reader)
    principalId: bootstrapIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource bootstrapArtifactContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(artifactContainer.id, bootstrapIdentity.id, roleIds.storageBlobDataContributor)
  scope: artifactContainer
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roleIds.storageBlobDataContributor
    )
    principalId: bootstrapIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2026-05-01' = {
  parent: project
  name: connectionNames.search
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${names.search}.search.windows.net'
    authType: 'AAD'
    isSharedToAll: false
    metadata: {
      ApiType: 'Azure'
      ResourceId: search.id
      Location: location
    }
  }
  dependsOn: [
    embeddingModel
  ]
}

// The 2026-05-15-preview schema omits ProjectManagedIdentity and audience.
// Preserve the existing Foundry preview wire contract, not ManagedIdentity
// (which would require a different credentials object). See infra/README.md.
resource knowledgeMcpConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2026-05-15-preview' = {
  parent: project
  name: connectionNames.knowledgeMcp
  properties: {
    category: 'RemoteTool'
    target: 'https://${names.search}.search.windows.net/knowledgebases/contoso-travel-knowledge-lab/mcp?api-version=2026-08-01-preview'
    #disable-next-line BCP036
    authType: 'ProjectManagedIdentity'
    useWorkspaceManagedIdentity: true
    isSharedToAll: false
    audience: 'https://search.azure.com'
    metadata: {
      ApiType: 'Azure'
    }
  }
  dependsOn: [
    searchConnection
    projectSearchIndexDataContributor
    projectSearchServiceContributor
  ]
}

resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2026-05-15-preview' = {
  parent: project
  name: connectionNames.appInsights
  properties: {
    category: 'AppInsights'
    target: appInsights.id
    #disable-next-line BCP036
    authType: 'ProjectManagedIdentity'
    isSharedToAll: false
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsights.id
      // Routing metadata stays inside this connection, never in context/outputs.
      ApplicationInsightsConnectionString: appInsights.properties.ConnectionString
    }
  }
  dependsOn: [
    knowledgeMcpConnection
    projectMonitoringMetricsPublisher
    projectLogAnalyticsReader
    projectMonitoringDataReader
  ]
}

var resourceOutputValues = {
  resource_group_name: { value: resourceGroup().name }
  location: { value: location }
  ai_services_account_name: { value: names.foundry }
  ai_services_endpoint: { value: foundry.properties.endpoint }
  openai_endpoint: { value: 'https://${names.foundry}.openai.azure.com/openai/v1/' }
  foundry_project_name: { value: names.project }
  foundry_project_id: { value: project.id }
  foundry_project_endpoint: { value: 'https://${names.foundry}.services.ai.azure.com/api/projects/${names.project}' }
  primary_model_deployment_name: { value: 'gpt-5.6-luna' }
  evaluation_model_deployment_name: { value: 'gpt-5.5' }
  optimizer_model_deployment_name: { value: 'gpt-5.5' }
  embedding_model_deployment_name: { value: 'embedding' }
  search_service_name: { value: names.search }
  search_service_endpoint: { value: 'https://${names.search}.search.windows.net' }
  search_pricing_model: { value: 'dedicated' }
  log_analytics_workspace_name: { value: names.logAnalytics }
  application_insights_name: { value: names.appInsights }
  application_insights_id: { value: appInsights.id }
  azureml_workspace_name: { value: names.azureml }
  azureml_workspace_id: { value: azureml.id }
  storage_account_name: { value: names.storage }
  storage_account_id: { value: storage.id }
  key_vault_name: { value: names.keyVault }
  key_vault_id: { value: keyVault.id }
  search_connection_name: { value: connectionNames.search }
  knowledge_mcp_connection_name: { value: connectionNames.knowledgeMcp }
  application_insights_connection_name: { value: connectionNames.appInsights }
  travel_api_fqdn: { value: travelApi.properties.configuration.ingress.fqdn }
  travel_api_container_app_name: { value: names.travelApi }
  foundry_portal_url: { value: 'https://ai.azure.com' }
}

var workshopContext = {
  schema_version: '1.0'
  provisioning_method: 'azure-custom-template'
  setup_status: 'infrastructure-ready'
  subscription_id: subscription().subscriptionId
  resource_group_name: resourceGroup().name
  location: location
  source_base: sourceBase
  source_revision: validatedSourceRevision
  participant_object_id: participantObjectId
  resource_outputs: resourceOutputValues
}

resource bootstrap 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: names.bootstrap
  location: location
  tags: tags
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${bootstrapIdentity.id}': {}
    }
  }
  properties: {
    // Azure Linux release predating CLI 2.88's embedded Python 3.14 change.
    // Dependency smoke tests do not replace regional Deployment Scripts E2E.
    azCliVersion: '2.87.0'
    // Windows worktrees can contain CRLF before Git normalization; bash cannot.
    scriptContent: replace(loadTextContent('../scripts/bootstrap-custom-template.sh'), '\r\n', '\n')
    environmentVariables: [
      {
        name: 'WORKSHOP_SOURCE_REVISION'
        value: validatedSourceRevision
      }
      {
        name: 'WORKSHOP_CONTEXT_JSON'
        value: string(workshopContext)
      }
      {
        name: 'WORKSHOP_ARTIFACT_CONTAINER'
        value: artifactContainer.name
      }
    ]
    timeout: 'PT1H'
    cleanupPreference: 'OnSuccess'
    retentionInterval: 'P1D'
    forceUpdateTag: guid(validatedSourceRevision, bootstrapRunId)
  }
  // Resource references add resource dependencies; the grants and connections
  // below must also finish before data-plane setup and participant validation.
  dependsOn: [
    primaryModel
    evaluationModel
    embeddingModel
    search
    searchConnection
    knowledgeMcpConnection
    appInsightsConnection
    participantFoundryUser
    participantProjectManager
    participantSearchServiceContributor
    participantSearchIndexDataContributor
    participantLogAnalyticsReader
    participantMonitoringDataReader
    participantAzuremlDataScientist
    participantStorageBlobDataContributor
    azuremlKeyVaultSecretsUser
    projectFoundryUser
    projectSearchIndexDataContributor
    projectSearchServiceContributor
    projectMonitoringMetricsPublisher
    projectLogAnalyticsReader
    projectMonitoringDataReader
    searchOpenAIUser
    bootstrapFoundryUser
    bootstrapSearchServiceContributor
    bootstrapSearchIndexDataContributor
    bootstrapReader
    bootstrapArtifactContributor
  ]
}

@description('Canonical non-secret resource_outputs mapping. The handoff ZIP contains the complete initialized context.')
output resourceOutputs object = resourceOutputValues

@description('Successful bootstrap artifact coordinates, source revision, and SHA-256. Use Storage browser > Microsoft Entra user account > Blob containers > workshop-files > Download.')
output participantDownload object = {
  status: bootstrap.properties.outputs.status
  storage_account_name: bootstrap.properties.outputs.storage_account_name
  container_name: bootstrap.properties.outputs.container_name
  blob_name: bootstrap.properties.outputs.blob_name
  sha256: bootstrap.properties.outputs.sha256
  source_revision: bootstrap.properties.outputs.source_revision
}

@description('Open this Storage account in Azure Portal, then use Storage browser and Microsoft Entra user account to download the private handoff ZIP.')
output storagePortalUrl string = 'https://portal.azure.com/#resource${storage.id}/overview'
