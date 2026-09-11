"""Static contracts for the compiled Portal template; no Azure calls or deployments."""

from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra"
FOUNDRY = "Microsoft.CognitiveServices/accounts"
PROJECT = f"{FOUNDRY}/projects"
MODELS = f"{FOUNDRY}/deployments"
CONNECTIONS = f"{PROJECT}/connections"
SEARCH = "Microsoft.Search/searchServices"
LOG_ANALYTICS = "Microsoft.OperationalInsights/workspaces"
APP_INSIGHTS = "Microsoft.Insights/components"
APP_ENVIRONMENT = "Microsoft.App/managedEnvironments"
APP = "Microsoft.App/containerApps"
STORAGE = "Microsoft.Storage/storageAccounts"
BLOB_SERVICE = f"{STORAGE}/blobServices"
CONTAINER = f"{BLOB_SERVICE}/containers"
KEY_VAULT = "Microsoft.KeyVault/vaults"
AML = "Microsoft.MachineLearningServices/workspaces"
UAMI = "Microsoft.ManagedIdentity/userAssignedIdentities"
ROLES = "Microsoft.Authorization/roleAssignments"
SCRIPT = "Microsoft.Resources/deploymentScripts"

ROLE_IDS = {
    "foundryUser": "53ca6127-db72-4b80-b1b0-d745d6d5456d",
    "foundryProjectManager": "eadc314b-1a2d-4efa-be10-5d325db5065e",
    "searchIndexDataContributor": "8ebe5a00-799e-43f5-93ac-243d3dce84a7",
    "searchServiceContributor": "7ca78c08-252a-4471-8644-bb5ff32d4ba0",
    "logAnalyticsReader": "73c42c96-874c-492b-b04d-ab87d138a893",
    "privilegedMonitoringDataReader": "dbc9c667-e97f-4491-aee6-90b9cf960190",
    "monitoringMetricsPublisher": "3913510d-42f4-4e42-8a64-420c390055eb",
    "cognitiveServicesOpenAIUser": "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd",
    "azuremlDataScientist": "f6c7c914-8db3-469d-8ca1-694a8f32e121",
    "storageBlobDataContributor": "ba92f5b4-2d11-453d-a403-e96b0029c9fe",
    "keyVaultSecretsUser": "4633458b-17de-408a-b874-0445c86b69e6",
    "reader": "acdd72a7-3385-48ef-bd42-f606fba81ae7",
}
OUTPUT_KEYS = {
    "resource_group_name",
    "location",
    "ai_services_account_name",
    "ai_services_endpoint",
    "openai_endpoint",
    "foundry_project_name",
    "foundry_project_id",
    "foundry_project_endpoint",
    "primary_model_deployment_name",
    "evaluation_model_deployment_name",
    "optimizer_model_deployment_name",
    "embedding_model_deployment_name",
    "search_service_name",
    "search_service_endpoint",
    "search_pricing_model",
    "log_analytics_workspace_name",
    "application_insights_name",
    "application_insights_id",
    "azureml_workspace_name",
    "azureml_workspace_id",
    "storage_account_name",
    "storage_account_id",
    "key_vault_name",
    "key_vault_id",
    "search_connection_name",
    "knowledge_mcp_connection_name",
    "application_insights_connection_name",
    "travel_api_fqdn",
    "travel_api_container_app_name",
    "foundry_portal_url",
}
PARAMETERS = {
    "location",
    "primaryModelVersion",
    "evaluationModelVersion",
    "embeddingModelVersion",
    "travelApiImageRef",
    "sourceRevision",
    "participantObjectIdOverride",
    "bootstrapRunId",
}
TOKEN = re.compile(r"\s*('(?:[^']|'')*'|[A-Za-z_$][\w$#]*|\d+|[(),.\[\]])")


def literal(value):
    return ("literal", value)


def call(name, *arguments):
    return ("call", name.lower(), tuple(arguments))


def prop(value, *names):
    for name in names:
        value = ("property", value, name)
    return value


@lru_cache(maxsize=1024)
def expression(text: str):
    """Parse the expression subset actually emitted here; never eval Python code."""
    assert text.startswith("[") and text.endswith("]")
    body = text[1:-1]
    tokens = []
    cursor = 0
    while cursor < len(body):
        match = TOKEN.match(body, cursor)
        assert match, f"Unsupported ARM expression at {body[cursor:]!r}"
        tokens.append(match.group(1))
        cursor = match.end()
    position = 0

    def consume(expected=None):
        nonlocal position
        token = tokens[position]
        position += 1
        if expected is not None:
            assert token == expected
        return token

    def parse():
        token = consume()
        if token.startswith("'"):
            value = literal(token[1:-1].replace("''", "'"))
        elif token.isdecimal():
            value = literal(int(token))
        else:
            consume("(")
            arguments = []
            if tokens[position] != ")":
                while True:
                    arguments.append(parse())
                    if tokens[position] != ",":
                        break
                    consume(",")
            consume(")")
            value = call(token, *arguments)
        while position < len(tokens) and tokens[position] == ".":
            consume(".")
            value = prop(value, consume())
        return value

    result = parse()
    assert position == len(tokens), f"Unconsumed ARM expression: {tokens[position:]}"
    return result


def node(value):
    if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
        return expression(value)
    return literal(value)


def unpack(value):
    """Compare JSON objects to equivalent ARM createObject expressions."""
    if value[0] == "literal":
        return value[1]
    if value[:2] == ("call", "createobject"):
        args = value[2]
        assert len(args) % 2 == 0
        result = {unpack(args[i]): unpack(args[i + 1]) for i in range(0, len(args), 2)}
        assert len(result) * 2 == len(args), "Duplicate ARM object key"
        return result
    if value[:2] == ("call", "json") and value[2][0][0] == "literal":
        return json.loads(value[2][0][1])
    return value


def normalized(value):
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalized(item) for item in value]
    return unpack(node(value))


def resources(template, kind):
    return [item for item in template["resources"] if item["type"] == kind]


def resource(template, kind):
    matches = resources(template, kind)
    assert len(matches) == 1
    return matches[0]


def resource_id(item):
    name = node(item["name"])
    parts = (name,)
    if name[:2] == ("call", "format"):
        arguments = name[2]
        assert arguments[0] == literal("/".join(f"{{{i}}}" for i in range(len(arguments) - 1)))
        parts = arguments[1:]
    if "scope" in item:
        return call("extensionResourceId", node(item["scope"]), literal(item["type"]), *parts)
    return call("resourceId", literal(item["type"]), *parts)


def reference(item, *properties, full=False):
    arguments = (resource_id(item), literal(item["apiVersion"]))
    if full:
        arguments += (literal("full"),)
    return prop(call("reference", *arguments), *properties)


class InputFailure(ValueError):
    pass


class InputExpressions:
    """Evaluate only pure input guards, not Azure resources or provider behavior."""

    def __init__(self, template, **parameters):
        self.template = template
        self.parameters = {
            key: value.get("defaultValue") for key, value in template["parameters"].items()
        } | parameters
        self.deployer_reads = 0

    def variable(self, name):
        return self.evaluate(node(self.template["variables"][name]))

    def evaluate(self, item, bindings=None):
        bindings = bindings or {}
        if item[0] == "literal":
            return item[1]
        if item[0] == "property":
            return self.evaluate(item[1], bindings)[item[2]]
        assert item[0] == "call"
        name, arguments = item[1:]
        if name == "if":
            branch = arguments[1] if self.evaluate(arguments[0], bindings) else arguments[2]
            return self.evaluate(branch, bindings)
        if name == "lambda":
            parameter = self.evaluate(arguments[0], bindings)
            return lambda value: self.evaluate(arguments[1], bindings | {parameter: value})
        args = [self.evaluate(argument, bindings) for argument in arguments]
        if name == "variables":
            return self.variable(args[0])
        if name == "parameters":
            return self.parameters[args[0]]
        if name == "lambdavariables":
            return bindings[args[0]]
        if name == "fail":
            raise InputFailure(args[0])
        if name == "deployer":
            self.deployer_reads += 1
            return {"objectId": "AAAAAAAA-0000-4000-8000-000000000001"}
        functions = {
            "and": lambda *values: all(values),
            "equals": lambda left, right: left == right,
            "empty": lambda value: not value,
            "filter": lambda values, predicate: [value for value in values if predicate(value)],
            "range": lambda start, count: list(range(start, start + count)),
            "not": lambda value: not value,
            "contains": lambda value, part: part in value,
            "length": len,
            "substring": lambda value, start, count: value[start : start + count],
            "split": lambda value, separator: value.split(separator),
            "first": lambda values: values[0],
            "last": lambda values: values[-1],
            "greaterorequals": lambda left, right: left >= right,
            "startswith": lambda value, prefix: value.lower().startswith(prefix.lower()),
            "tolower": str.lower,
            "format": lambda value, *parts: value.format(*parts),
        }
        assert name in functions, f"Unsupported input function: {name}"
        return functions[name](*args)


@pytest.fixture(scope="module")
def template():
    return json.loads((INFRA / "azuredeploy.json").read_text(encoding="utf-8-sig"))


def test_template_is_compiled_resource_group_only_with_an_exact_inventory(template):
    assert template["$schema"] == (
        "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
    )
    assert template["metadata"]["_generator"]["name"] == "bicep"
    assert template["metadata"]["_generator"]["templateHash"].isdecimal()
    assert not any(key.startswith("_EXPERIMENTAL") for key in template["metadata"])
    expected = Counter(
        {
            FOUNDRY: 1,
            PROJECT: 1,
            MODELS: 3,
            SEARCH: 1,
            LOG_ANALYTICS: 1,
            APP_INSIGHTS: 1,
            APP_ENVIRONMENT: 1,
            APP: 1,
            STORAGE: 1,
            BLOB_SERVICE: 1,
            CONTAINER: 1,
            KEY_VAULT: 1,
            AML: 1,
            UAMI: 1,
            ROLES: 21,
            CONNECTIONS: 3,
            SCRIPT: 1,
        }
    )
    assert Counter(item["type"] for item in template["resources"]) == expected
    ids = {resource_id(item) for item in template["resources"]}
    assert len(ids) == len(template["resources"])
    for item in template["resources"]:
        assert (
            not {"subscriptionId", "resourceGroup", "resources", "condition", "copy"} & item.keys()
        )
        if "scope" in item:
            assert item["type"] == ROLES
            assert node(item["scope"]) in ids
    assert "targetScope = 'resourceGroup'" in (INFRA / "main.bicep").read_text(encoding="utf-8")


def test_exact_parameter_boundary_and_inert_example(template):
    parameters = template["parameters"]
    assert parameters.keys() == PARAMETERS
    assert all(item["type"] == "string" for item in parameters.values())
    assert parameters["location"]["allowedValues"] == ["japaneast"]
    assert parameters["location"]["defaultValue"] == "japaneast"
    assert {name for name, value in parameters.items() if "defaultValue" in value} == {
        "location",
        "participantObjectIdOverride",
        "bootstrapRunId",
    }
    for model in ("primary", "evaluation", "embedding"):
        assert parameters[f"{model}ModelVersion"]["minLength"] >= 1
    assert parameters["sourceRevision"]["minLength"] == 40
    assert parameters["sourceRevision"]["maxLength"] == 40
    assert parameters["travelApiImageRef"]["minLength"] >= 83
    assert parameters["travelApiImageRef"]["maxLength"] <= 256
    assert parameters["participantObjectIdOverride"]["defaultValue"] == ""
    assert parameters["bootstrapRunId"]["defaultValue"] == "1"
    example = json.loads(
        (INFRA / "azuredeploy.parameters.example.json").read_text(encoding="utf-8")
    )
    assert example["parameters"].keys() == PARAMETERS
    assert all(item.keys() == {"value"} for item in example["parameters"].values())
    for model in ("primary", "evaluation", "embedding"):
        assert example["parameters"][f"{model}ModelVersion"]["value"] == (
            "REPLACE_WITH_ADMIN_VERIFIED_VERSION"
        )
    inputs = InputExpressions(
        template, **{key: value["value"] for key, value in example["parameters"].items()}
    )
    with pytest.raises(InputFailure):
        inputs.variable("validatedSourceRevision")
    with pytest.raises(InputFailure):
        inputs.variable("validatedTravelApiImageRef")


@pytest.mark.parametrize("revision", ["0123456789abcdef" * 2 + "01234567", "0" * 40])
def test_valid_source_revisions_are_preserved(template, revision):
    inputs = InputExpressions(template, sourceRevision=revision)
    assert inputs.variable("validatedSourceRevision") == revision
    assert inputs.variable("sourceBase") == (
        f"https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/{revision}"
    )


@pytest.mark.parametrize(
    "revision",
    [
        "",
        "main",
        "dev-custom-template",
        "a" * 39,
        "a" * 41,
        "A" * 40,
        "g" * 40,
        "a" * 39 + "/",
        "a" * 39 + "\n",
        "a" * 39 + " ",
    ],
)
def test_invalid_source_revisions_fail_without_a_fallback(template, revision):
    inputs = InputExpressions(template, sourceRevision=revision)
    with pytest.raises(InputFailure, match="sourceRevision"):
        inputs.variable("validatedSourceRevision")
    with pytest.raises(InputFailure, match="sourceRevision"):
        inputs.variable("sourceBase")


@pytest.mark.parametrize(
    "repository",
    ["ghcr.io/a/b", "ghcr.io/example/contoso-travel-api", "ghcr.io/owner/nested/image.v2"],
)
def test_immutable_ghcr_digest_passes_through_unchanged(template, repository):
    image = repository + "@sha256:" + "0123456789abcdef" * 4
    assert (
        InputExpressions(template, travelApiImageRef=image).variable("validatedTravelApiImageRef")
        == image
    )


@pytest.mark.parametrize(
    "image",
    [
        "ghcr.io/a/b:latest",
        "ghcr.io/a/b:latest@sha256:" + "a" * 64,
        "docker.io/a/b@sha256:" + "a" * 64,
        "GHCR.IO/a/b@sha256:" + "a" * 64,
        "ghcr.io/A/b@sha256:" + "a" * 64,
        "ghcr.io/b@sha256:" + "a" * 64,
        "ghcr.io//b@sha256:" + "a" * 64,
        "ghcr.io/a/../b@sha256:" + "a" * 64,
        "ghcr.io/a/./b@sha256:" + "a" * 64,
        "ghcr.io/a/b/@sha256:" + "a" * 64,
        "ghcr.io/a/b@sha256:" + "a" * 63,
        "ghcr.io/a/b@sha256:" + "a" * 65,
        "ghcr.io/a/b@sha256:" + "A" * 64,
        "ghcr.io/a/b@sha256:" + "g" * 64,
        "ghcr.io/a/b@sha512:" + "a" * 64,
        "ghcr.io/a/b@sha256:" + "a" * 64 + "@sha256:" + "b" * 64,
        "ghcr.io/a/b@sha256:" + "a" * 64 + "?tag=latest",
        "ghcr.io/a/b@sha256:" + "a" * 63 + "\n",
        "ghcr.io/a/%62@sha256:" + "a" * 64,
        "https://ghcr.io/a/b@sha256:" + "a" * 64,
    ],
)
def test_mutable_or_malformed_images_are_rejected_before_consumption(template, image):
    with pytest.raises(InputFailure, match="travelApiImageRef"):
        InputExpressions(template, travelApiImageRef=image).variable("validatedTravelApiImageRef")
    container = resource(template, APP)["properties"]["template"]["containers"][0]
    assert container["image"] == "[variables('validatedTravelApiImageRef')]"


def test_participant_is_resolved_once_and_is_not_the_bootstrap_identity(template):
    inputs = InputExpressions(template)
    assert inputs.variable("participantObjectId") == "aaaaaaaa-0000-4000-8000-000000000001"
    assert inputs.deployer_reads == 1
    override = "BBBBBBBB-0000-4000-8000-000000000002"
    proxy = InputExpressions(template, participantObjectIdOverride=override)
    assert proxy.variable("participantObjectId") == override.lower()
    assert proxy.deployer_reads == 0
    source = (INFRA / "main.bicep").read_text(encoding="utf-8")
    assert source.count("deployer()") == 1
    assert "userPrincipalName" not in source


def test_resource_names_do_not_change_when_source_or_run_id_changes(template):
    assert template["variables"]["nameSuffix"] == (
        "[uniqueString(resourceGroup().id, parameters('location'))]"
    )
    expected_prefixes = {
        "foundry": "aif-fdyws-",
        "search": "srch-fdyws-",
        "logAnalytics": "log-fdyws-",
        "appInsights": "appi-fdyws-",
        "containerEnvironment": "cae-fdyws-",
        "travelApi": "ca-travel-api-",
        "azureml": "mlw-fdyws-",
        "storage": "stfdyws",
        "keyVault": "kv-fdyws-",
        "bootstrapIdentity": "id-fdyws-bootstrap-",
        "bootstrap": "ds-fdyws-bootstrap-",
    }
    names = template["variables"]["names"]
    assert names.keys() == expected_prefixes.keys() | {"project"}
    assert names["project"] == "contoso-travel"
    for key, prefix in expected_prefixes.items():
        assert node(names[key]) == call(
            "format", literal(prefix + "{0}"), expression("[variables('nameSuffix')]")
        )
    source = (INFRA / "main.bicep").read_text(encoding="utf-8")
    assert "newGuid(" not in source
    assert "utcNow(" not in source
    for item in template["resources"]:
        if "location" in item:
            assert item["location"] == "[parameters('location')]"


def test_foundry_and_search_keep_the_keyless_basic_configuration(template):
    foundry = resource(template, FOUNDRY)
    assert foundry["apiVersion"] == "2026-05-01"
    assert foundry["kind"] == "AIServices"
    assert foundry["sku"] == {"name": "S0"}
    assert foundry["properties"] == {
        "allowProjectManagement": True,
        "customSubDomainName": foundry["name"],
        "disableLocalAuth": True,
        "publicNetworkAccess": "Enabled",
        "networkAcls": {"defaultAction": "Allow"},
    }
    search = resource(template, SEARCH)
    assert search["apiVersion"] == "2025-05-01"
    assert search["sku"] == {"name": "basic"}
    assert search["properties"] == {
        "partitionCount": 1,
        "replicaCount": 1,
        "semanticSearch": "free",
        "disableLocalAuth": True,
        "publicNetworkAccess": "Enabled",
    }
    for kind in (FOUNDRY, PROJECT, SEARCH, APP, AML):
        assert resource(template, kind)["identity"] == {"type": "SystemAssigned"}


def test_three_models_have_fixed_capacities_versions_and_sequential_dependencies(template):
    models = resources(template, MODELS)
    assert len(models) == 3
    previous = resource(template, PROJECT)
    for model_name, deployment, capacity, parameter in [
        ("gpt-5.6-luna", "gpt-5.6-luna", 40, "primaryModelVersion"),
        ("gpt-5.5", "gpt-5.5", 100, "evaluationModelVersion"),
        ("text-embedding-3-small", "embedding", 40, "embeddingModelVersion"),
    ]:
        model = next(item for item in models if item["properties"]["model"]["name"] == model_name)
        assert model["apiVersion"] == "2026-05-01"
        assert model["sku"] == {"name": "GlobalStandard", "capacity": capacity}
        assert model["properties"] == {
            "model": {
                "format": "OpenAI",
                "name": model_name,
                "version": f"[parameters('{parameter}')]",
            }
        }
        assert node(model["name"]) == call(
            "format",
            literal("{0}/{1}"),
            node(resource(template, FOUNDRY)["name"]),
            literal(deployment),
        )
        assert resource_id(previous) in {node(value) for value in model["dependsOn"]}
        previous = model


def test_monitoring_and_container_api_preserve_existing_settings(template):
    logs = resource(template, LOG_ANALYTICS)
    insights = resource(template, APP_INSIGHTS)
    assert logs["properties"]["sku"] == {"name": "PerGB2018"}
    assert logs["properties"]["retentionInDays"] == 30
    assert insights["kind"] == "web"
    assert insights["properties"]["Application_Type"] == "web"
    assert insights["properties"]["DisableLocalAuth"] is True
    assert node(insights["properties"]["WorkspaceResourceId"]) == resource_id(logs)
    logging = resource(template, APP_ENVIRONMENT)["properties"]["appLogsConfiguration"]
    assert logging["destination"] == "log-analytics"
    assert node(logging["logAnalyticsConfiguration"]["customerId"]) == reference(logs, "customerId")
    assert node(logging["logAnalyticsConfiguration"]["sharedKey"]) == prop(
        call("listKeys", resource_id(logs), literal(logs["apiVersion"])), "primarySharedKey"
    )
    app = resource(template, APP)["properties"]
    assert node(app["managedEnvironmentId"]) == resource_id(resource(template, APP_ENVIRONMENT))
    assert app["configuration"] == {
        "activeRevisionsMode": "Single",
        "ingress": {
            "external": True,
            "targetPort": 8080,
            "transport": "auto",
            "allowInsecure": False,
            "traffic": [{"latestRevision": True, "weight": 100}],
        },
    }
    assert app["template"]["scale"] == {"minReplicas": 0, "maxReplicas": 1}
    assert normalized(app["template"]["containers"]) == [
        {
            "name": "travel-api",
            "image": expression("[variables('validatedTravelApiImageRef')]"),
            "resources": {"cpu": 0.25, "memory": "0.5Gi"},
            "env": [
                {"name": "WORKSHOP_SOURCE_BASE", "value": expression("[variables('sourceBase')]")}
            ],
        }
    ]


def test_aml_storage_is_private_oauth_default_without_breaking_shared_key_compatibility(template):
    storage = resource(template, STORAGE)
    assert storage["kind"] == "StorageV2"
    assert storage["sku"] == {"name": "Standard_LRS"}
    assert storage["properties"] == {
        "accessTier": "Hot",
        "publicNetworkAccess": "Enabled",
        "supportsHttpsTrafficOnly": True,
        "minimumTlsVersion": "TLS1_2",
        "allowSharedKeyAccess": True,
        "allowBlobPublicAccess": False,
        "defaultToOAuthAuthentication": True,
    }
    container = resource(template, CONTAINER)
    assert container["properties"] == {"publicAccess": "None"}
    assert node(container["name"]) == call(
        "format",
        literal("{0}/{1}/{2}"),
        node(storage["name"]),
        literal("default"),
        literal("workshop-files"),
    )
    vault = resource(template, KEY_VAULT)
    assert vault["properties"]["enableRbacAuthorization"] is True
    assert vault["properties"]["accessPolicies"] == []
    assert vault["properties"]["publicNetworkAccess"] == "Enabled"
    assert vault["properties"]["softDeleteRetentionInDays"] == 7
    assert "enablePurgeProtection" not in vault["properties"]
    workspace = resource(template, AML)
    assert workspace["apiVersion"] == "2025-06-01"
    assert workspace["sku"] == {"name": "Basic", "tier": "Basic"}
    assert normalized(workspace["properties"]) == {
        "applicationInsights": resource_id(resource(template, APP_INSIGHTS)),
        "keyVault": resource_id(vault),
        "storageAccount": resource_id(storage),
        "publicNetworkAccess": "Enabled",
        "hbiWorkspace": False,
        "v1LegacyMode": False,
    }


def expected_grants(template):
    principal = expression("[variables('participantObjectId')]")
    project = reference(resource(template, PROJECT), "identity", "principalId", full=True)
    search = reference(resource(template, SEARCH), "identity", "principalId", full=True)
    aml = reference(resource(template, AML), "identity", "principalId", full=True)
    bootstrap = reference(resource(template, UAMI), "principalId")
    entries = [
        (principal, "User", FOUNDRY, "foundryUser"),
        (principal, "User", PROJECT, "foundryProjectManager"),
        (principal, "User", SEARCH, "searchServiceContributor"),
        (principal, "User", SEARCH, "searchIndexDataContributor"),
        (principal, "User", LOG_ANALYTICS, "logAnalyticsReader"),
        (principal, "User", APP_INSIGHTS, "privilegedMonitoringDataReader"),
        (principal, "User", AML, "azuremlDataScientist"),
        (principal, "User", STORAGE, "storageBlobDataContributor"),
        (aml, "ServicePrincipal", KEY_VAULT, "keyVaultSecretsUser"),
        (project, "ServicePrincipal", FOUNDRY, "foundryUser"),
        (project, "ServicePrincipal", SEARCH, "searchIndexDataContributor"),
        (project, "ServicePrincipal", SEARCH, "searchServiceContributor"),
        (project, "ServicePrincipal", APP_INSIGHTS, "monitoringMetricsPublisher"),
        (project, "ServicePrincipal", APP_INSIGHTS, "logAnalyticsReader"),
        (project, "ServicePrincipal", APP_INSIGHTS, "privilegedMonitoringDataReader"),
        (search, "ServicePrincipal", FOUNDRY, "cognitiveServicesOpenAIUser"),
        (bootstrap, "ServicePrincipal", FOUNDRY, "foundryUser"),
        (bootstrap, "ServicePrincipal", SEARCH, "searchServiceContributor"),
        (bootstrap, "ServicePrincipal", SEARCH, "searchIndexDataContributor"),
        (bootstrap, "ServicePrincipal", None, "reader"),
        (bootstrap, "ServicePrincipal", CONTAINER, "storageBlobDataContributor"),
    ]
    return {
        (
            identity,
            kind,
            resource_id(resource(template, scope)) if scope else expression("[resourceGroup().id]"),
            call(
                "subscriptionResourceId",
                literal("Microsoft.Authorization/roleDefinitions"),
                prop(expression("[variables('roleIds')]"), role),
            ),
        )
        for identity, kind, scope, role in entries
    }


def test_all_rbac_grants_are_exact_scoped_and_do_not_duplicate_the_aml_automatic_grant(template):
    assert template["variables"]["roleIds"] == ROLE_IDS
    grants = resources(template, ROLES)
    actual = {
        (
            node(item["properties"]["principalId"]),
            item["properties"]["principalType"],
            node(item.get("scope", "[resourceGroup().id]")),
            node(item["properties"]["roleDefinitionId"]),
        )
        for item in grants
    }
    assert len(actual) == len(grants) == 21
    assert actual == expected_grants(template)
    for item in grants:
        assert item["apiVersion"] == "2022-04-01"
        assert item["properties"].keys() == {"principalId", "principalType", "roleDefinitionId"}
        name = node(item["name"])
        assert name[:2] == ("call", "guid")
        assert len(name[2]) == 3
        assert name[2][0] == node(item.get("scope", "[resourceGroup().id]"))
        assert name[2][2] == node(item["properties"]["roleDefinitionId"])[2][1]
        principal = node(item["properties"]["principalId"])
        if item["properties"]["principalType"] == "User":
            assert name[2][1] == principal
        else:
            assert name[2][1] in {
                resource_id(resource(template, kind)) for kind in (PROJECT, SEARCH, AML, UAMI)
            }


def test_connections_preserve_the_complete_preview_wire_contract(template):
    connections = {
        item["properties"]["category"]: item for item in resources(template, CONNECTIONS)
    }
    names = template["variables"]["connectionNames"]
    assert names == {
        "search": "contoso-travel-search",
        "knowledgeMcp": "contoso-travel-knowledge-lab-mcp",
        "appInsights": "contoso-travel-appinsights",
    }
    search = connections["CognitiveSearch"]
    assert search["apiVersion"] == "2026-05-01"
    assert normalized(search["properties"]) == {
        "category": "CognitiveSearch",
        "target": expression(
            "[format('https://{0}.search.windows.net', variables('names').search)]"
        ),
        "authType": "AAD",
        "isSharedToAll": False,
        "metadata": {
            "ApiType": "Azure",
            "ResourceId": resource_id(resource(template, SEARCH)),
            "Location": expression("[parameters('location')]"),
        },
    }
    mcp = connections["RemoteTool"]
    assert mcp["apiVersion"] == "2026-05-15-preview"
    assert normalized(mcp["properties"]) == {
        "category": "RemoteTool",
        "target": expression(
            "[format('https://{0}.search.windows.net/knowledgebases/"
            "contoso-travel-knowledge-lab/mcp?api-version=2026-08-01-preview', "
            "variables('names').search)]"
        ),
        "authType": "ProjectManagedIdentity",
        "useWorkspaceManagedIdentity": True,
        "isSharedToAll": False,
        "audience": "https://search.azure.com",
        "metadata": {"ApiType": "Azure"},
    }
    insights = connections["AppInsights"]
    assert insights["apiVersion"] == "2026-05-15-preview"
    assert normalized(insights["properties"]) == {
        "category": "AppInsights",
        "target": resource_id(resource(template, APP_INSIGHTS)),
        "authType": "ProjectManagedIdentity",
        "isSharedToAll": False,
        "metadata": {
            "ApiType": "Azure",
            "ResourceId": resource_id(resource(template, APP_INSIGHTS)),
            "ApplicationInsightsConnectionString": reference(
                resource(template, APP_INSIGHTS), "ConnectionString"
            ),
        },
    }
    for category, key in (
        ("CognitiveSearch", "search"),
        ("RemoteTool", "knowledgeMcp"),
        ("AppInsights", "appInsights"),
    ):
        assert node(connections[category]["name"]) == call(
            "format",
            literal("{0}/{1}/{2}"),
            node(resource(template, FOUNDRY)["name"]),
            expression("[variables('names').project]"),
            prop(expression("[variables('connectionNames')]"), key),
        )
    source = (INFRA / "main.bicep").read_text(encoding="utf-8")
    assert re.findall(r"#disable-next-line ([^\r\n]+)", source) == ["BCP036", "BCP036"]
    assert (
        len(re.findall(r"#disable-next-line BCP036\s+authType: 'ProjectManagedIdentity'", source))
        == 2
    )
    assert re.search(r"\bany\s*\(", source) is None


def test_bootstrap_has_a_dedicated_identity_private_artifact_and_bounded_lifecycle(template):
    script = resource(template, SCRIPT)
    assert script["apiVersion"] == "2023-08-01"
    assert script["kind"] == "AzureCLI"
    identity = script["identity"]
    assert identity.keys() == {"type", "userAssignedIdentities"}
    assert identity["type"] == "UserAssigned"
    assert len(identity["userAssignedIdentities"]) == 1
    identity_id, settings = next(iter(identity["userAssignedIdentities"].items()))
    assert node(identity_id) == call(
        "format", literal("{0}"), resource_id(resource(template, UAMI))
    )
    assert settings == {}
    properties = script["properties"]
    assert properties.keys() == {
        "azCliVersion",
        "scriptContent",
        "environmentVariables",
        "timeout",
        "cleanupPreference",
        "retentionInterval",
        "forceUpdateTag",
    }
    assert properties["azCliVersion"] == "2.87.0"
    assert properties["timeout"] == "PT1H"
    assert properties["cleanupPreference"] == "OnSuccess"
    assert properties["retentionInterval"] == "P1D"
    assert node(properties["forceUpdateTag"]) == call(
        "guid",
        expression("[variables('validatedSourceRevision')]"),
        expression("[parameters('bootstrapRunId')]"),
    )
    environment = properties["environmentVariables"]
    assert len(environment) == 3
    assert all(item.keys() == {"name", "value"} for item in environment)
    values = {item["name"]: item["value"] for item in environment}
    assert values.keys() == {
        "WORKSHOP_SOURCE_REVISION",
        "WORKSHOP_CONTEXT_JSON",
        "WORKSHOP_ARTIFACT_CONTAINER",
    }
    assert values["WORKSHOP_SOURCE_REVISION"] == "[variables('validatedSourceRevision')]"
    assert values["WORKSHOP_ARTIFACT_CONTAINER"] == "workshop-files"


def test_bootstrap_waits_for_every_resource_connection_and_grant(template):
    graph = {
        resource_id(item): {node(dependency) for dependency in item.get("dependsOn", [])}
        for item in template["resources"]
    }
    script = resource_id(resource(template, SCRIPT))
    assert {
        resource_id(item)
        for item in template["resources"]
        if item["type"] in (ROLES, CONNECTIONS, MODELS)
    } <= graph[script]
    visited = set()

    def visit(identifier, ancestors):
        assert identifier not in ancestors, "Dependency cycle"
        assert identifier in graph, "Dependency escapes the template's RG"
        if identifier in visited:
            return
        for dependency in graph[identifier]:
            visit(dependency, ancestors | {identifier})
        visited.add(identifier)

    visit(script, set())
    assert visited == graph.keys(), "An infrastructure resource can race bootstrap"


def test_embedded_script_is_the_actual_entrypoint_normalized_for_linux(template):
    content = node(resource(template, SCRIPT)["properties"]["scriptContent"])
    assert content[:2] == ("call", "replace")
    file_content, original, replacement = content[2]
    assert original == literal("\r\n")
    assert replacement == literal("\n")
    assert file_content[:2] == ("call", "variables")
    embedded = template["variables"][file_content[2][0][1]]
    source = (ROOT / "scripts" / "bootstrap-custom-template.sh").read_bytes().decode("utf-8")
    assert embedded == source
    executable = embedded.replace(original[1], replacement[1])
    assert "\r" not in executable, "CRLF breaks the Linux Deployment Scripts shell"
    assert executable.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
    assert executable.endswith("\nPY\n")
    assert len(executable) <= 32000
    assert "loadTextContent('../scripts/bootstrap-custom-template.sh')" in (
        INFRA / "main.bicep"
    ).read_text(encoding="utf-8")


def test_resource_outputs_and_embedded_context_have_the_exact_canonical_shape(template):
    outputs = template["outputs"]
    assert outputs.keys() == {"resourceOutputs", "participantDownload", "storagePortalUrl"}
    assert outputs["resourceOutputs"]["type"] == "object"
    values = outputs["resourceOutputs"]["value"]
    assert values.keys() == OUTPUT_KEYS
    assert all(item.keys() == {"value"} and item["value"] for item in values.values())
    for key, kind in [
        ("ai_services_account_name", FOUNDRY),
        ("search_service_name", SEARCH),
        ("log_analytics_workspace_name", LOG_ANALYTICS),
        ("application_insights_name", APP_INSIGHTS),
        ("azureml_workspace_name", AML),
        ("storage_account_name", STORAGE),
        ("key_vault_name", KEY_VAULT),
        ("travel_api_container_app_name", APP),
    ]:
        assert values[key]["value"] == resource(template, kind)["name"]
    for key, kind in [
        ("foundry_project_id", PROJECT),
        ("application_insights_id", APP_INSIGHTS),
        ("azureml_workspace_id", AML),
        ("storage_account_id", STORAGE),
        ("key_vault_id", KEY_VAULT),
    ]:
        assert node(values[key]["value"]) == resource_id(resource(template, kind))
    for key, expected in {
        "resource_group_name": "[resourceGroup().name]",
        "location": "[parameters('location')]",
        "foundry_project_name": "[variables('names').project]",
        "primary_model_deployment_name": "gpt-5.6-luna",
        "evaluation_model_deployment_name": "gpt-5.5",
        "optimizer_model_deployment_name": "gpt-5.5",
        "embedding_model_deployment_name": "embedding",
        "search_pricing_model": "dedicated",
        "foundry_portal_url": "https://ai.azure.com",
        "search_connection_name": "[variables('connectionNames').search]",
        "knowledge_mcp_connection_name": "[variables('connectionNames').knowledgeMcp]",
        "application_insights_connection_name": "[variables('connectionNames').appInsights]",
    }.items():
        assert values[key]["value"] == expected
    assert node(values["ai_services_endpoint"]["value"]) == reference(
        resource(template, FOUNDRY), "endpoint"
    )
    assert node(values["travel_api_fqdn"]["value"]) == reference(
        resource(template, APP), "configuration", "ingress", "fqdn"
    )
    for key, pattern in [
        ("openai_endpoint", "https://{0}.openai.azure.com/openai/v1/"),
        ("search_service_endpoint", "https://{0}.search.windows.net"),
        ("foundry_project_endpoint", "https://{0}.services.ai.azure.com/api/projects/{1}"),
    ]:
        arguments = (
            node(
                resource(template, SEARCH if key == "search_service_endpoint" else FOUNDRY)["name"]
            ),
        )
        if key == "foundry_project_endpoint":
            arguments += (expression("[variables('names').project]"),)
        assert node(values[key]["value"]) == call("format", literal(pattern), *arguments)
    environment = resource(template, SCRIPT)["properties"]["environmentVariables"]
    serialized = node(
        next(item["value"] for item in environment if item["name"] == "WORKSHOP_CONTEXT_JSON")
    )
    assert serialized[:2] == ("call", "string")
    assert unpack(serialized[2][0]) == {
        "schema_version": "1.0",
        "provisioning_method": "azure-custom-template",
        "setup_status": "infrastructure-ready",
        "subscription_id": expression("[subscription().subscriptionId]"),
        "resource_group_name": expression("[resourceGroup().name]"),
        "location": expression("[parameters('location')]"),
        "source_base": expression("[variables('sourceBase')]"),
        "source_revision": expression("[variables('validatedSourceRevision')]"),
        "participant_object_id": expression("[variables('participantObjectId')]"),
        "resource_outputs": normalized(values),
    }


def test_download_outputs_are_allowlisted_script_results_not_invented_success_or_credentials(
    template,
):
    download = template["outputs"]["participantDownload"]
    assert download["type"] == "object"
    assert download["value"].keys() == {
        "status",
        "storage_account_name",
        "container_name",
        "blob_name",
        "sha256",
        "source_revision",
    }
    for key, value in download["value"].items():
        assert node(value) == reference(resource(template, SCRIPT), "outputs", key)
    surfaces = {
        "outputs": template["outputs"],
        "environment": resource(template, SCRIPT)["properties"]["environmentVariables"],
    }
    serialized = json.dumps(surfaces).lower()
    for forbidden in (
        "connectionstring",
        "listkeys(",
        "sharedkey",
        "accountkey",
        "clientsecret",
        "access_token",
        "sig=",
        "credentials",
        "primaryendpoints.blob",
    ):
        assert forbidden not in serialized
    assert node(template["outputs"]["storagePortalUrl"]["value"]) == call(
        "format",
        literal("https://portal.azure.com/#resource{0}/overview"),
        resource_id(resource(template, STORAGE)),
    )
