from __future__ import annotations

import hashlib


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def workspace_id_from_root(root_path: str) -> str:
    return f"workspace:{stable_hash(root_path)[:16]}"


def provider_id(provider: str) -> str:
    return f"provider:{provider}"


def source_ref_id(provider: str, source_ref: str) -> str:
    return f"source:{provider}:{stable_hash(source_ref)}"


def project_id(provider: str, project_key: str) -> str:
    return f"project:{provider}:{stable_hash(project_key)}"


def scanner_id(scanner_id_value: str, scanner_version: str) -> str:
    return f"scanner:{scanner_id_value}:{scanner_version}"


def session_id(provider: str, session_id_value: str) -> str:
    return f"session:{provider}:{session_id_value}"


def chat_event_id(provider: str, session_id_value: str, event_id: str) -> str:
    return f"chat_event:{provider}:{session_id_value}:{event_id}"


def event_stub_id(provider: str, session_id_value: str, event_id: str) -> str:
    return f"event_stub:{provider}:{session_id_value}:{event_id}"


def factor_id(factor_id_value: str, version: str = "") -> str:
    if version:
        return f"factor:{factor_id_value}:{version}"
    return f"factor_stub:{factor_id_value}"


def analysis_run_id(analysis_run_id_value: str) -> str:
    return f"analysis_run:{analysis_run_id_value}"


def factor_result_id(result_run_id: str) -> str:
    return f"factor_result:{result_run_id}"


def tag_id(tag_type: str, tag_value: str) -> str:
    return f"tag:{tag_type}:{tag_value}"


def tag_assertion_id(result_run_id: str, target_node_id: str, tag_type: str, tag_value: str) -> str:
    return f"tag_assertion:{result_run_id}:{target_node_id}:{tag_type}:{tag_value}"


def dataset_id(result_run_id: str, dataset_id_value: str) -> str:
    return f"dataset:{result_run_id}:{dataset_id_value}"


def dataset_record_id(result_run_id: str, dataset_id_value: str, record_id: str) -> str:
    return f"dataset_record:{result_run_id}:{dataset_id_value}:{record_id}"


def presentation_id(result_run_id: str, presentation_id_value: str) -> str:
    return f"presentation:{result_run_id}:{presentation_id_value}"


def route_id(route_area: str, route_key: str) -> str:
    return f"route:{route_area}:{route_key}"


def run_error_id(analysis_run_id_value: str, factor_id_value: str, ordinal: int) -> str:
    return f"run_error:{analysis_run_id_value}:{factor_id_value}:{ordinal}"


def target_stub_id(target_type: str, target_id: str) -> str:
    return f"target_stub:{target_type}:{target_id}"


def target_type_id(target_type: str) -> str:
    return f"target_type:{target_type}"
