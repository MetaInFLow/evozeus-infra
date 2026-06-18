from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from html import escape
import json
from typing import Any

from evozeus.factors.packs import FactorPack
from evozeus.factors.protocol import FactorResult
from evozeus.reports.visualizations import ResultVisualization, build_result_visualizations


def render_factor_results_html(
    session_id: str,
    results: list[FactorResult],
    factor_packs: list[FactorPack],
    selected_factor_ids: Iterable[str] | None = None,
    session_statuses: Iterable[Any] | None = None,
    session_events: Iterable[Any] | None = None,
) -> str:
    selected_ids = set(selected_factor_ids) if selected_factor_ids is not None else None
    pack_by_id = {pack.manifest.id: pack for pack in factor_packs}
    selected_results = [
        result
        for result in results
        if selected_ids is None or result.factor_id in selected_ids
    ]
    visualizations = build_result_visualizations(selected_results)
    payload = _report_payload(session_id, selected_results, visualizations, pack_by_id, session_statuses, session_events)
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>EvoZeus Factor Results - {escape(session_id)}</title>",
            '  <link rel="icon" href="data:,">',
            '  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/antd@5/dist/reset.css">',
            "  <style>",
            _style(),
            "  </style>",
            "</head>",
            "<body>",
            '  <div id="evozeus-dashboard-root"></div>',
            _fallback_html(payload),
            "  <script>",
            f"    window.__EVOZEUS_REPORT__ = {_safe_json(payload)};",
            "  </script>",
            '  <script crossorigin src="https://cdn.jsdelivr.net/npm/react@18/umd/react.production.min.js"></script>',
            '  <script crossorigin src="https://cdn.jsdelivr.net/npm/react-dom@18/umd/react-dom.production.min.js"></script>',
            '  <script crossorigin src="https://cdn.jsdelivr.net/npm/dayjs@1/dayjs.min.js"></script>',
            '  <script crossorigin src="https://cdn.jsdelivr.net/npm/antd@5/dist/antd.min.js"></script>',
            "  <script>",
            _dashboard_script(),
            "  </script>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _report_payload(
    session_id: str,
    results: list[FactorResult],
    visualizations: list[ResultVisualization],
    pack_by_id: dict[str, FactorPack],
    session_statuses: Iterable[Any] | None,
    session_events: Iterable[Any] | None,
) -> dict[str, Any]:
    result_items = [_result_payload(result, pack_by_id.get(result.factor_id)) for result in results]
    summary = _summary_payload(results)
    return {
        "renderer": "Ant Design dashboard",
        "session": {
            "id": session_id,
            "result_count": len(results),
        },
        "sessions": _session_payloads(session_id, summary, session_statuses),
        "session_events": _session_event_payloads(session_events, pack_by_id),
        "summary": summary,
        "visualizations": [_visualization_payload(visualization) for visualization in visualizations],
        "results": result_items,
        "factor_packs": [_factor_pack_payload(pack) for pack in pack_by_id.values()],
    }


def _session_payloads(
    current_session_id: str,
    current_summary: dict[str, Any],
    session_statuses: Iterable[Any] | None,
) -> list[dict[str, Any]]:
    if session_statuses is None:
        return [
            {
                "key": current_session_id,
                "session_id": current_session_id,
                "provider": "codex",
                "is_current": True,
                "result_count": current_summary["total"],
                "matched": current_summary["matched"],
                "skipped": current_summary["skipped"],
                "top_verdict": current_summary["top_verdict"],
                "analyzed_factor_count": current_summary["total"],
                "pending_factor_count": 0,
                "last_analyzed_at": "",
                "first_user_preview": "",
                "first_user_source_ref": "",
                "first_user_source_line": 0,
                "last_assistant_preview": "",
                "last_assistant_source_ref": "",
                "last_assistant_source_line": 0,
                "session_title": current_session_id,
                "session_cwd": "",
                "session_group_key": "Ungrouped",
                "session_group_label": "Ungrouped",
                "session_updated_at": "",
            }
        ]
    rows = []
    for status in session_statuses:
        session_id = str(getattr(status, "session_id", ""))
        is_current = session_id == current_session_id
        rows.append(
            {
                "key": session_id,
                "session_id": session_id,
                "provider": str(getattr(status, "provider", "")),
                "is_current": is_current,
                "source_ref": str(getattr(status, "source_ref", "")),
                "event_count": int(getattr(status, "event_count", 0)),
                "result_count": current_summary["total"] if is_current else int(getattr(status, "analyzed_factor_count", 0)),
                "matched": current_summary["matched"] if is_current else 0,
                "skipped": current_summary["skipped"] if is_current else 0,
                "top_verdict": current_summary["top_verdict"] if is_current else "待分析",
                "analyzed_factor_count": int(getattr(status, "analyzed_factor_count", 0)),
                "pending_factor_count": int(getattr(status, "pending_factor_count", 0)),
                "last_analyzed_at": str(getattr(status, "last_analyzed_at", "")),
                "stale_reason": str(getattr(status, "stale_reason", "")),
                "first_user_preview": str(getattr(status, "first_user_preview", "")),
                "first_user_source_ref": str(getattr(status, "first_user_source_ref", "")),
                "first_user_source_line": int(getattr(status, "first_user_source_line", 0)),
                "last_assistant_preview": str(getattr(status, "last_assistant_preview", "")),
                "last_assistant_source_ref": str(getattr(status, "last_assistant_source_ref", "")),
                "last_assistant_source_line": int(getattr(status, "last_assistant_source_line", 0)),
                "session_title": str(getattr(status, "session_title", "") or session_id),
                "session_cwd": str(getattr(status, "session_cwd", "")),
                "session_group_key": str(getattr(status, "session_group_key", "") or "Ungrouped"),
                "session_group_label": str(getattr(status, "session_group_label", "") or "Ungrouped"),
                "session_updated_at": str(getattr(status, "session_updated_at", "")),
            }
        )
    return rows


def _session_event_payloads(session_events: Iterable[Any] | None, pack_by_id: dict[str, FactorPack]) -> list[dict[str, Any]]:
    if session_events is None:
        return []
    rows = []
    for event in session_events:
        rows.append(
            {
                "key": f"{getattr(event, 'session_id', '')}:{getattr(event, 'event_id', '')}",
                "session_id": str(getattr(event, "session_id", "")),
                "event_id": str(getattr(event, "event_id", "")),
                "event_index": int(getattr(event, "event_index", 0)),
                "role": str(getattr(event, "role", "")),
                "content": str(getattr(event, "content", "")),
                "tool_name": str(getattr(event, "tool_name", "")),
                "tool_result_preview": str(getattr(event, "tool_result_preview", "")),
                "source_ref": str(getattr(event, "source_ref", "")),
                "source_line": int(getattr(event, "source_line", 0)),
                "tags": [_event_tag_payload(tag, pack_by_id) for tag in getattr(event, "tags", [])],
            }
        )
    return rows


def _event_tag_payload(tag: Any, pack_by_id: dict[str, FactorPack]) -> dict[str, str]:
    factor_id = str(getattr(tag, "factor_id", ""))
    tag_type = str(getattr(tag, "tag_type", ""))
    tag_value = str(getattr(tag, "tag_value", ""))
    pack = pack_by_id.get(factor_id)
    intro = pack.introduction if pack is not None else None
    label = _find_tag_label(pack, tag_type, tag_value)
    label_zh = label.label_zh if label is not None else ""
    label_en = label.label_en if label is not None else ""
    return {
        "factor_id": factor_id,
        "factor_name": intro.name if intro is not None else factor_id,
        "factor_name_zh": intro.name_zh if intro is not None else "",
        "factor_name_en": intro.name_en if intro is not None else "",
        "factor_summary": intro.summary if intro is not None else "",
        "factor_summary_zh": intro.summary_zh if intro is not None else "",
        "factor_summary_en": intro.summary_en if intro is not None else "",
        "type": tag_type,
        "value": tag_value,
        "label": _bilingual_display(label_zh, label_en) if label_zh and label_en else "",
        "label_zh": label_zh,
        "label_en": label_en,
        "reason": str(getattr(tag, "reason", "")),
        "result_run_id": str(getattr(tag, "result_run_id", "")),
    }


def _summary_payload(results: list[FactorResult]) -> dict[str, Any]:
    status_counts = Counter(result.status for result in results)
    verdict_counts = Counter(verdict for result in results for verdict in result.verdict_signals)
    evidence_ref_count = sum(len(result.evidence_refs) for result in results)
    confidence_values = [result.confidence for result in results if result.status == "matched"]
    average_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0
    return {
        "total": len(results),
        "matched": status_counts.get("matched", 0),
        "skipped": status_counts.get("skipped", 0),
        "evidence_refs": evidence_ref_count,
        "top_verdict": verdict_counts.most_common(1)[0][0] if verdict_counts else "None",
        "average_confidence": _round_float(average_confidence),
        "status_counts": dict(status_counts),
        "verdict_counts": dict(verdict_counts),
    }


def _result_payload(result: FactorResult, pack: FactorPack | None) -> dict[str, Any]:
    intro = pack.introduction if pack is not None else None
    return {
        "key": result.factor_id,
        "factor_id": result.factor_id,
        "factor_name": intro.name if intro is not None else result.factor_id,
        "factor_name_zh": intro.name_zh if intro is not None else "",
        "factor_name_en": intro.name_en if intro is not None else "",
        "summary": intro.summary if intro is not None else "",
        "summary_zh": intro.summary_zh if intro is not None else "",
        "summary_en": intro.summary_en if intro is not None else "",
        "version": result.factor_version or "unknown",
        "stage": result.stage.value,
        "status": result.status,
        "confidence": _round_float(result.confidence),
        "verdict_signals": result.verdict_signals,
        "tags": [
            _result_tag_payload(tag, pack)
            for tag in result.tags
        ],
        "scores": [
            {"key": key, "value": _round_float(value)}
            for key, value in result.scores.items()
        ],
        "evidence_refs": [
            {
                "id": str(ref.get("event_id") or ref.get("ref_id") or ""),
                "kind": str(ref.get("kind") or ref.get("source") or "event"),
            }
            for ref in result.evidence_refs
        ],
    }


def _visualization_payload(visualization: ResultVisualization) -> dict[str, Any]:
    return {
        "component": visualization.component,
        "title": visualization.title,
        "description": visualization.description,
        "input_fields": visualization.input_fields,
        "output_fields": visualization.output_fields,
        "terms": [
            {
                "text": term.text,
                "weight": term.weight,
                "source_factor_ids": term.source_factor_ids,
            }
            for term in visualization.terms
        ],
    }


def _factor_pack_payload(pack: FactorPack) -> dict[str, Any]:
    intro = pack.introduction
    return {
        "key": pack.manifest.id,
        "factor_id": pack.manifest.id,
        "name": intro.name,
        "name_zh": intro.name_zh,
        "name_en": intro.name_en,
        "version": pack.manifest.version,
        "stage": pack.manifest.stage.value,
        "runtime": pack.manifest.runtime.mode.value,
        "summary": intro.summary,
        "summary_zh": intro.summary_zh,
        "summary_en": intro.summary_en,
        "when_to_use": intro.when_to_use,
        "when_to_use_zh": intro.when_to_use_zh,
        "when_to_use_en": intro.when_to_use_en,
        "limitations": intro.limitations,
        "limitations_zh": intro.limitations_zh,
        "limitations_en": intro.limitations_en,
        "category": intro.category,
        "privacy": intro.privacy,
        "privacy_zh": intro.privacy_zh,
        "privacy_en": intro.privacy_en,
        "tag_labels": [
            {
                "type": label.type,
                "value": label.value,
                "label": _bilingual_display(label.label_zh, label.label_en),
                "label_zh": label.label_zh,
                "label_en": label.label_en,
            }
            for label in intro.tag_labels
        ],
    }


def _result_tag_payload(tag: dict[str, str], pack: FactorPack | None) -> dict[str, str]:
    tag_type = str(tag.get("type") or "")
    tag_value = str(tag.get("value") or "")
    label = _find_tag_label(pack, tag_type, tag_value)
    label_zh = label.label_zh if label is not None else ""
    label_en = label.label_en if label is not None else ""
    return {
        "type": tag_type,
        "value": tag_value,
        "label": _bilingual_display(label_zh, label_en) if label_zh and label_en else "",
        "label_zh": label_zh,
        "label_en": label_en,
    }


def _find_tag_label(pack: FactorPack | None, tag_type: str, tag_value: str) -> Any | None:
    if pack is None:
        return None
    exact = [
        label
        for label in pack.introduction.tag_labels
        if label.type == tag_type and label.value == tag_value
    ]
    if exact:
        return exact[0]
    wildcard = [
        label
        for label in pack.introduction.tag_labels
        if label.type == tag_type and label.value == "*"
    ]
    return wildcard[0] if wildcard else None


def _bilingual_display(zh: str, en: str) -> str:
    return f"{zh} / {en}"


def _fallback_html(payload: dict[str, Any]) -> str:
    results = payload["results"]
    cards = "\n".join(
        [
            (
                f'      <section data-result-card="factor_result" data-status="{escape(result["status"], quote=True)}">'
                f'<strong>{escape(result["factor_name"])}</strong>'
                f'<span>{escape(result["status"].title())}</span>'
                f'<p>{escape(result["factor_id"])}</p>'
                f'<p>{" ".join(escape(str(score["value"])) for score in result["scores"])}</p>'
                "</section>"
            )
            for result in results
        ]
    )
    return "\n".join(
        [
            "  <noscript>",
            '    <main class="dashboard-shell fallback">',
            '      <section data-workspace-tab="sessions"><h2>Sessions</h2></section>',
            '      <section data-workspace-tab="dashboards"><h2>Dashboards</h2></section>',
            '      <section data-workspace-tab="factor_packs"><h2>Factor Packs</h2></section>',
            '      <section data-component="workspace_coverage"></section>',
            '      <section data-component="result_summary">',
            f'        <strong>Matched</strong><span>{payload["summary"]["matched"]}</span>',
            f'        <strong>Skipped</strong><span>{payload["summary"]["skipped"]}</span>',
            "      </section>",
            '      <section data-component="word_cloud"></section>',
            cards,
            "    </main>",
            "  </noscript>",
        ]
    )


def _safe_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _round_float(value: float) -> float:
    return round(float(value), 3)


def _dashboard_script() -> str:
    return r"""
    (() => {
      const h = React.createElement;
      const { App, Badge, Button, Card, Col, Drawer, Empty, Progress, Row, Space, Statistic, Table, Tabs, Tag, Tooltip, Typography } = antd;
      const { Text, Title } = Typography;
      const data = window.__EVOZEUS_REPORT__;

      function statusColor(status) {
        if (status === "matched") return "success";
        if (status === "skipped") return "default";
        return "warning";
      }

      function verdictColor(verdict) {
        if (verdict === "Fix Environment") return "red";
        if (verdict === "Open Case") return "gold";
        if (verdict === "Promote to Skill") return "blue";
        if (verdict === "待分析") return "gold";
        return "default";
      }

      function pendingFactorLabel(count) {
        const normalized = Number(count || 0);
        return normalized > 0 ? `待分析 ${normalized} 个因子` : "分析完成";
      }

      function pendingGroupLabel(count) {
        const normalized = Number(count || 0);
        return normalized > 0 ? `${normalized} 个因子待分析` : "分析完成";
      }

      function bilingualText(zh, en, fallback) {
        if (zh && en) return `${zh} / ${en}`;
        return zh || en || fallback || "";
      }

      function readableTag(tag) {
        return bilingualText(tag.label_zh, tag.label_en, tag.label || `${tag.type}:${tag.value}`);
      }

      function Summary() {
        const summary = data.summary;
        return h("section", {"data-component": "result_summary", className: "summary-panel"},
          h(Row, { gutter: [12, 12] },
            h(Col, { xs: 12, md: 6 }, h(Card, { size: "small" }, h(Statistic, { title: "Results", value: summary.total }))),
            h(Col, { xs: 12, md: 6 }, h(Card, { size: "small" }, h(Statistic, { title: "Matched", value: summary.matched, valueStyle: { color: "#1677ff" } }))),
            h(Col, { xs: 12, md: 6 }, h(Card, { size: "small" }, h(Statistic, { title: "Skipped", value: summary.skipped }))),
            h(Col, { xs: 12, md: 6 }, h(Card, { size: "small" }, h(Statistic, { title: "Avg Confidence", value: summary.average_confidence, precision: 3 })))
          ),
          h(Card, { size: "small", className: "verdict-strip" },
            h(Space, { wrap: true, size: [8, 8] },
              h(Text, { type: "secondary" }, "Top verdict"),
              h(Tag, { color: verdictColor(summary.top_verdict) }, summary.top_verdict),
              h(Text, { type: "secondary" }, "Evidence refs"),
              h(Tag, null, summary.evidence_refs)
            )
          )
        );
      }

      function WordCloud() {
        const cloud = data.visualizations.find((item) => item.component === "word_cloud");
        const terms = (cloud && cloud.terms || []).slice(0, 32);
        return h(Card, { title: cloud ? cloud.title : "高频信号词云", "data-component": "word_cloud", className: "dashboard-card" },
          h("p", { className: "card-note" }, cloud ? cloud.description : ""),
          h("div", { className: "word-cloud" },
            terms.length ? terms.map((term) =>
              h(Tag, {
                key: term.text,
                color: term.weight > 1 ? "blue" : "default",
                style: { fontSize: `${Math.min(26, 12 + term.weight * 3)}px` },
                title: term.source_factor_ids.join(", ")
              }, term.text)
            ) : h(Text, { type: "secondary" }, "No terms")
          )
        );
      }

      function WorkspaceCoverage() {
        const sessions = data.sessions || [];
        const analyzedSessions = sessions.filter((session) => session.analyzed_factor_count > 0).length;
        const pendingFactorRuns = sessions.reduce((total, session) => total + (session.pending_factor_count || 0), 0);
        return h("section", { "data-component": "workspace_coverage", className: "summary-panel" },
          h(Row, { gutter: [12, 12] },
            h(Col, { xs: 12, md: 8 }, h(Card, { size: "small" }, h(Statistic, { title: "Scanned Sessions", value: sessions.length }))),
            h(Col, { xs: 12, md: 8 }, h(Card, { size: "small" }, h(Statistic, { title: "Analyzed Sessions", value: analyzedSessions }))),
            h(Col, { xs: 24, md: 8 }, h(Card, { size: "small" }, h(Statistic, { title: "待分析因子运行", value: pendingFactorRuns })))
          )
        );
      }

      function ResultTable({ onOpen }) {
        const columns = [
          {
            title: "Factor",
            dataIndex: "factor_name",
            render: (_, row) => h("div", null,
              h(Text, { strong: true }, row.factor_name),
              h("br"),
              h(Text, { type: "secondary" }, row.factor_id)
            )
          },
          {
            title: "Status",
            dataIndex: "status",
            width: 110,
            render: (status) => h(Badge, { status: statusColor(status), text: status })
          },
          {
            title: "Verdict",
            dataIndex: "verdict_signals",
            render: (items) => h(Space, { wrap: true, size: [4, 4] },
              (items.length ? items : ["None"]).map((item) => h(Tag, { key: item, color: verdictColor(item) }, item))
            )
          },
          {
            title: "Confidence",
            dataIndex: "confidence",
            width: 140,
            render: (value) => h(Progress, { percent: Math.round(value * 100), size: "small" })
          },
          {
            title: "",
            dataIndex: "action",
            width: 96,
            render: (_, row) => h("a", { onClick: () => onOpen(row) }, "Details")
          }
        ];
        return h(Card, { title: "Factor Result Matrix", className: "dashboard-card", "data-component": "factor_result_matrix" },
          h(Table, { columns, dataSource: data.results, pagination: false, size: "small" })
        );
      }

      function Tags({ items }) {
        if (!items.length) return h(Text, { type: "secondary" }, "None");
        return h(Space, { wrap: true, size: [4, 6] },
          items.map((item) => h(Tag, { key: item }, item))
        );
      }

      function ResultDetail({ result }) {
        if (!result) return null;
        return h("section", { "data-result-card": "factor_result", "data-status": result.status, className: `result-detail status-${result.status}` },
          h("p", { className: "card-note" }, bilingualText(result.summary_zh, result.summary_en, result.summary)),
          h("div", { className: "result-section" }, h(Text, { strong: true }, "Verdict"), h(Tags, { items: result.verdict_signals })),
          h("div", { className: "result-section" }, h(Text, { strong: true }, "Tags"), h(Tags, { items: result.tags.map((tag) => `${readableTag(tag)} (${tag.type}=${tag.value})`) })),
          h("div", { className: "result-section" }, h(Text, { strong: true }, "Scores"), h(Tags, { items: result.scores.map((score) => `${score.key}=${score.value}`) })),
          h("div", { className: "result-section" }, h(Text, { strong: true }, "Evidence"), h(Tags, { items: result.evidence_refs.map((ref) => `${ref.id} (${ref.kind})`) }))
        );
      }

      function SourceLine({ label, sourceRef, sourceLine }) {
        if (!sourceRef && !sourceLine) return null;
        return h("div", { className: "source-line" },
          h(Text, { type: "secondary" }, label),
          h("br"),
          h(Text, { code: true }, sourceLine ? `${sourceRef}:${sourceLine}` : sourceRef)
        );
      }

      function eventsForSession(sessionId) {
        return (data.session_events || []).filter((event) => event.session_id === sessionId);
      }

      function visibleEventsForSession(sessionId) {
        return dedupeVisibleEvents(eventsForSession(sessionId).filter((event) => {
          const hasBody = Boolean(event.content || event.tool_result_preview);
          const hasTags = Boolean((event.tags || []).length);
          if (hasBody || hasTags) return true;
          return !["event", "reasoning"].includes(event.role);
        }));
      }

      function dedupeVisibleEvents(events) {
        return events.filter((event, index) => {
          const previous = events[index - 1];
          if (!previous) return true;
          return !(
            previous.role === event.role
            && (previous.content || previous.tool_result_preview || "") === (event.content || event.tool_result_preview || "")
          );
        });
      }

      function timestampValue(value) {
        const parsed = Number(value || 0);
        return Number.isFinite(parsed) ? parsed : 0;
      }

      function buildSessionGroups(sessions) {
        const byKey = new Map();
        sessions.forEach((session) => {
          const key = session.session_group_key || "Ungrouped";
          if (!byKey.has(key)) {
            byKey.set(key, {
              key,
              label: session.session_group_label || key,
              cwd: session.session_cwd || "",
              latestUpdatedAt: 0,
              sessions: []
            });
          }
          const group = byKey.get(key);
          group.sessions.push(session);
          group.latestUpdatedAt = Math.max(group.latestUpdatedAt, timestampValue(session.session_updated_at));
        });
        const groups = Array.from(byKey.values());
        groups.forEach((group) => {
          group.sessions.sort((left, right) => (
            timestampValue(right.session_updated_at) - timestampValue(left.session_updated_at)
            || String(left.session_title || left.session_id).localeCompare(String(right.session_title || right.session_id), "zh-CN")
          ));
        });
        groups.sort((left, right) => (
          right.latestUpdatedAt - left.latestUpdatedAt
          || String(left.label).localeCompare(String(right.label), "zh-CN")
        ));
        return groups;
      }

      function signalInitial(tag) {
        const value = String(tag.label_zh || tag.factor_name_zh || tag.type || tag.factor_id || "signal").trim();
        return value ? value.slice(0, 1).toUpperCase() : "S";
      }

      function signalTooltip(tag) {
        const tagLabel = readableTag(tag);
        const factorName = bilingualText(tag.factor_name_zh, tag.factor_name_en, tag.factor_name || tag.factor_id);
        const factorSummary = bilingualText(tag.factor_summary_zh, tag.factor_summary_en, tag.factor_summary);
        return [
          tagLabel,
          `Factor: ${factorName}`,
          `Raw: ${tag.type}:${tag.value}`,
          factorSummary,
          tag.reason ? `原因: ${tag.reason}` : ""
        ].filter(Boolean).join("\n");
      }

      function EventSignalRail({ event }) {
        const tags = event.tags || [];
        if (tags.length) {
          return h("div", { className: "event-signal-rail has-signals", "data-component": "event_signal_rail" },
            h("div", { className: "event-signal-count" }, tags.length),
            tags.slice(0, 5).map((tag) =>
              h(Tooltip, { key: `${tag.factor_id}:${tag.type}:${tag.value}`, title: signalTooltip(tag), placement: "left" },
                h("span", { className: "event-signal-icon", "data-component": "event_signal_icon" }, signalInitial(tag))
              )
            ),
            tags.length > 5 ? h(Tooltip, { title: `${tags.length - 5} more signals`, placement: "left" },
              h("span", { className: "event-signal-more" }, `+${tags.length - 5}`)
            ) : null
          );
        }
        return h("div", { className: "event-signal-rail empty", "data-component": "event_signal_rail" });
      }

      function ChatEvent({ event, session, onOpen }) {
        const isAssistant = event.role === "assistant";
        const isUser = event.role === "user";
        const isComplete = event.role === "task_complete";
        const roleColor = isUser ? "blue" : isAssistant ? "green" : isComplete ? "purple" : "default";
        const body = event.content || event.tool_result_preview || "";
        return h("button", {
          type: "button",
          className: `chat-event role-${event.role}`,
          onClick: () => onOpen(event)
        },
          h("div", { className: "chat-event-main" },
            h("div", { className: "chat-event-meta" },
              h(Tag, { color: roleColor }, event.role || "event"),
              event.tool_name ? h(Text, { type: "secondary" }, event.tool_name) : null,
              h(Text, { type: "secondary" }, `#${event.event_index}`)
            ),
            h("div", { className: "chat-event-content" }, body || "Empty event")
          ),
          h(EventSignalRail, { event, session })
        );
      }

      function EventDetail({ event }) {
        if (!event) return null;
        const tags = event.tags || [];
        return h("section", { className: "event-detail" },
          h("div", { className: "result-section" }, h(Text, { strong: true }, "Event"), h(Tags, { items: [event.event_id, event.role, event.tool_name].filter(Boolean) })),
          h("div", { className: "result-section" }, h(Text, { strong: true }, "Content"), h("p", null, event.content || event.tool_result_preview || "")),
          event.tool_result_preview ? h("div", { className: "result-section" }, h(Text, { strong: true }, "Tool Result"), h("p", null, event.tool_result_preview)) : null,
          h("div", { className: "result-section" }, h(Text, { strong: true }, "Tags"), h(Tags, { items: tags.map((tag) => `${readableTag(tag)} · ${bilingualText(tag.factor_name_zh, tag.factor_name_en, tag.factor_name || tag.factor_id)}`) })),
          h(SourceLine, { label: "Source locator", sourceRef: event.source_ref, sourceLine: event.source_line })
        );
      }

      function SessionConversation({ session, onBack }) {
        const [drawerEvent, setDrawerEvent] = React.useState(null);
        const events = visibleEventsForSession(session.session_id);
        return h("section", { className: "session-conversation", "data-component": "session_conversation" },
          h("div", { className: "conversation-header" },
            h(Button, { onClick: onBack }, "Sessions"),
            h("div", null,
              h(Title, { level: 3 }, session.session_id),
              h(Space, { size: 6, wrap: true },
                h(Tag, null, session.provider),
                session.session_title && session.session_title !== session.session_id ? h(Tag, null, session.session_title) : null,
                session.session_group_label ? h(Tag, null, session.session_group_label) : null,
                h(Tag, null, `${session.event_count || events.length} events`),
                h(Tag, { color: session.pending_factor_count ? "gold" : "green" }, pendingFactorLabel(session.pending_factor_count))
              )
            )
          ),
          events.length
            ? h("div", { className: "chat-timeline" }, events.map((event) => h(ChatEvent, { key: event.key, event, session, onOpen: setDrawerEvent })))
            : h(Empty, { description: "No events" }),
          h(Drawer, {
            title: drawerEvent ? `${drawerEvent.role} · ${drawerEvent.event_id}` : "Event",
            width: 560,
            open: Boolean(drawerEvent),
            onClose: () => setDrawerEvent(null)
          }, h(EventDetail, { event: drawerEvent }))
        );
      }

      function SessionsTab() {
        const [selectedSessionId, setSelectedSessionId] = React.useState(null);
        const selectedSession = selectedSessionId
          ? data.sessions.find((session) => session.session_id === selectedSessionId)
          : null;
        if (selectedSession) {
          return h(SessionConversation, { session: selectedSession, onBack: () => setSelectedSessionId(null) });
        }
        const sessionGroups = buildSessionGroups(data.sessions || []);
        const columns = [
          {
            title: "Session",
            dataIndex: "session_id",
            render: (value, row) => h("div", { className: "session-cell" },
              h(Button, { type: "link", className: "session-link", onClick: () => setSelectedSessionId(row.session_id) }, row.session_title || value),
              h(Space, { size: 6, className: "session-meta" },
                h(Tag, null, row.provider),
                h(Text, { code: true }, value),
                row.event_count ? h(Text, { type: "secondary" }, `${row.event_count} events`) : null
              ),
              row.first_user_preview ? h("div", { className: "session-preview" },
                h(Text, { type: "secondary" }, "User · "),
                h(Text, null, row.first_user_preview)
              ) : null,
              row.last_assistant_preview ? h("div", { className: "session-preview assistant" },
                h(Text, { type: "secondary" }, "Assistant · "),
                h(Text, null, row.last_assistant_preview)
              ) : null
            )
          },
          { title: "Results", dataIndex: "result_count", width: 100 },
          { title: "Matched", dataIndex: "matched", width: 100 },
          { title: "Analyzed", dataIndex: "analyzed_factor_count", width: 110 },
          {
            title: "待分析",
            dataIndex: "pending_factor_count",
            width: 100,
            render: (value) => h(Tag, { color: value ? "gold" : "green" }, value ? `${value} 个因子` : "完成")
          },
          {
            title: "Top Verdict",
            dataIndex: "top_verdict",
            render: (value) => h(Tag, { color: verdictColor(value) }, value)
          }
        ];
        return h("section", { "data-workspace-tab": "sessions", className: "workspace-tab" },
          h("div", { className: "session-folder-groups", "data-component": "session_folder_groups" },
            sessionGroups.length ? sessionGroups.map((group) =>
              h("section", { key: group.key, className: "session-folder-group" },
                h("div", { className: "session-folder-header" },
                  h("div", null,
                    h(Text, { strong: true }, group.label),
                    group.cwd ? h("div", { className: "session-folder-path" }, h(Text, { type: "secondary" }, group.cwd)) : null
                  ),
                  h(Space, { size: 6 },
                    h(Tag, null, `${group.sessions.length} sessions`),
                    h(Tag, { color: group.sessions.some((session) => session.pending_factor_count) ? "gold" : "green" },
                      pendingGroupLabel(group.sessions.reduce((total, session) => total + (session.pending_factor_count || 0), 0))
                    )
                  )
                ),
                h(Table, {
                  columns,
                  dataSource: group.sessions,
                  pagination: false,
                  size: "small"
                })
              )
            ) : h(Empty, { description: "No sessions" })
          )
        );
      }

      function DashboardsTab({ onOpen }) {
        return h("section", { "data-workspace-tab": "dashboards", className: "workspace-tab" },
          h(WorkspaceCoverage),
          h(Summary),
          h(Row, { gutter: [16, 16], className: "dashboard-row" },
            h(Col, { xs: 24, lg: 10 }, h(WordCloud)),
            h(Col, { xs: 24, lg: 14 }, h(ResultTable, { onOpen }))
          )
        );
      }

      function FactorPacksTab() {
        const columns = [
          {
            title: "Factor",
            dataIndex: "name",
            render: (_, row) => h("div", null,
              h(Text, { strong: true }, row.name),
              h("br"),
              h(Text, { type: "secondary" }, row.factor_id)
            )
          },
          { title: "Stage", dataIndex: "stage", width: 180 },
          { title: "Runtime", dataIndex: "runtime", width: 140 },
          { title: "Version", dataIndex: "version", width: 110 }
        ];
        return h("section", { "data-workspace-tab": "factor_packs", className: "workspace-tab" },
          h(Table, {
            columns,
            dataSource: data.factor_packs,
            pagination: false,
            size: "small",
            expandable: {
              expandedRowRender: (row) => h("div", { className: "pack-detail" },
                h("p", null, bilingualText(row.summary_zh, row.summary_en, row.summary)),
                h("p", null, bilingualText(row.when_to_use_zh, row.when_to_use_en, row.when_to_use)),
                h(Text, { type: "secondary" }, bilingualText(row.privacy_zh, row.privacy_en, row.privacy))
              )
            }
          })
        );
      }

      function Dashboard() {
        const [drawerResult, setDrawerResult] = React.useState(null);
        return h(App, null,
          h("main", { className: "dashboard-shell" },
            h("header", { className: "dashboard-header" },
              h("div", null,
                h(Text, { type: "secondary" }, "EvoZeus Workspace · Ant Design"),
                h(Title, { level: 1 }, data.session.id)
              ),
              h(Tag, { color: "blue" }, `${data.session.result_count} results`)
            ),
            h(Tabs, {
              items: [
                { key: "sessions", label: "Sessions", children: h(SessionsTab) },
                { key: "dashboards", label: "Dashboards", children: h(DashboardsTab, { onOpen: setDrawerResult }) },
                { key: "factor_packs", label: "Factor Packs", children: h(FactorPacksTab) }
              ]
            }),
            h(Drawer, {
              title: drawerResult ? drawerResult.factor_name : "Factor Result",
              width: 520,
              open: Boolean(drawerResult),
              onClose: () => setDrawerResult(null)
            },
              h(ResultDetail, { result: drawerResult })
            )
          )
        );
      }

      ReactDOM.createRoot(document.getElementById("evozeus-dashboard-root")).render(h(Dashboard));
    })();
    """.strip()


def _style() -> str:
    return """
    :root { color-scheme: light; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #f5f7fb; color: #141414; }
    .dashboard-shell { max-width: 1180px; margin: 0 auto; padding: 32px 20px 48px; }
    .dashboard-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; border-bottom: 1px solid #d9d9d9; margin-bottom: 18px; padding-bottom: 16px; }
    .dashboard-header h1 { margin: 4px 0 0; font-size: 30px; line-height: 1.18; }
    .summary-panel { display: grid; gap: 12px; margin-bottom: 16px; }
    .workspace-tab { padding-top: 4px; }
    .verdict-strip { border-color: #d6e4ff; background: #f8fbff; }
    .dashboard-row { margin-bottom: 16px; }
    .dashboard-card { height: 100%; border-radius: 8px; }
    .card-note { color: #5f6b7a; line-height: 1.55; margin: 0 0 12px; }
    .word-cloud { display: flex; flex-wrap: wrap; gap: 9px; align-items: center; padding-top: 2px; }
    .word-cloud .ant-tag { margin-inline-end: 0; line-height: 1.7; }
    .result-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .result-card { border-radius: 8px; }
    .result-card.status-matched { border-left: 4px solid #1677ff; }
    .result-card.status-skipped { border-left: 4px solid #d9d9d9; }
    .result-detail { display: grid; gap: 10px; }
    .pack-detail { color: #5f6b7a; line-height: 1.55; max-width: 820px; }
    .result-section { border-top: 1px solid #f0f0f0; padding-top: 10px; margin-top: 10px; display: grid; gap: 7px; }
    .session-cell { display: grid; gap: 5px; max-width: 560px; }
    .session-link { height: auto; padding: 0; font-weight: 600; justify-self: start; }
    .session-meta { margin-top: 1px; }
    .session-preview { line-height: 1.45; overflow-wrap: anywhere; }
    .session-preview.assistant { color: #5f6b7a; }
    .source-line { overflow-wrap: anywhere; }
    .session-folder-groups { display: grid; gap: 14px; }
    .session-folder-group { background: #fff; border: 1px solid #edf0f5; border-radius: 8px; overflow: hidden; }
    .session-folder-header { min-height: 52px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 16px; background: #fbfcff; border-bottom: 1px solid #edf0f5; }
    .session-folder-path { margin-top: 3px; overflow-wrap: anywhere; }
    .session-conversation { display: grid; gap: 14px; }
    .conversation-header { display: flex; gap: 14px; align-items: flex-start; border-bottom: 1px solid #edf0f5; padding-bottom: 14px; }
    .conversation-header h3 { margin: 0 0 8px; }
    .chat-timeline { display: grid; gap: 10px; }
    .chat-event { width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) 104px; gap: 16px; align-items: start; text-align: left; background: #fff; border: 1px solid #edf0f5; border-radius: 8px; padding: 12px 14px; cursor: pointer; font: inherit; color: inherit; }
    .chat-event:hover { border-color: #91caff; background: #fbfdff; }
    .chat-event.role-user { border-left: 3px solid #1677ff; }
    .chat-event.role-assistant { border-left: 3px solid #52c41a; }
    .chat-event.role-tool { border-left: 3px solid #8c8c8c; }
    .chat-event-main { min-width: 0; display: grid; gap: 8px; }
    .chat-event-meta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
    .chat-event-content { line-height: 1.58; white-space: pre-wrap; overflow-wrap: anywhere; }
    .event-signal-rail { display: flex; justify-content: flex-end; align-items: flex-start; flex-wrap: wrap; gap: 6px; min-height: 28px; }
    .event-signal-rail.empty { opacity: 0; pointer-events: none; }
    .event-signal-count { min-width: 22px; height: 22px; padding: 0 6px; border-radius: 999px; background: #f0f5ff; color: #0958d9; border: 1px solid #adc6ff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; line-height: 1; }
    .event-signal-icon { width: 24px; height: 24px; border-radius: 50%; background: #e6f4ff; color: #0958d9; border: 1px solid #91caff; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; line-height: 1; box-shadow: 0 1px 2px rgba(5, 57, 128, 0.08); }
    .event-signal-more { min-width: 24px; height: 24px; padding: 0 5px; border-radius: 999px; background: #f5f5f5; color: #595959; border: 1px solid #d9d9d9; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; line-height: 1; }
    .event-detail { display: grid; gap: 8px; }
    .fallback { display: block; }
    @media (max-width: 760px) {
      .dashboard-shell { padding: 22px 14px 36px; }
      .dashboard-header { align-items: flex-start; flex-direction: column; }
      .dashboard-header h1 { font-size: 24px; overflow-wrap: anywhere; }
      .result-grid { grid-template-columns: 1fr; }
      .conversation-header { flex-direction: column; }
      .chat-event { grid-template-columns: 1fr; }
      .event-signal-rail { justify-content: flex-start; }
    }
    """.strip()
