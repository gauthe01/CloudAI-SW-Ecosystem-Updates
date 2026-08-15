"use client";

import { useEffect, useMemo, useState } from "react";

import {
  type AdminTopicUpdate,
  listAdminTopicUpdates,
} from "@/features/admin/admin-topic-updates-api";

export function AdminEventsTopicsPanel() {
  const [topics, setTopics] = useState<AdminTopicUpdate[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    listAdminTopicUpdates({ search })
      .then((payload) => {
        if (mounted) {
          setTopics(payload.topics);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Unable to load Events/Topics.");
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [search]);

  const groupedTopics = useMemo(() => groupTopics(topics), [topics]);

  return (
    <div className="admin-team-panel events-topics-panel">
      <div className="admin-panel-heading">
        <div>
          <p className="eyebrow">Global approved knowledge</p>
          <h2>Events/Topics</h2>
          <p>Approved non-partner updates visible to all presenters for their reporting month.</p>
        </div>
        <label className="admin-search-control">
          <span>Search</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search topics or update text"
          />
        </label>
      </div>

      {error ? <div className="form-banner error">{error}</div> : null}

      <div className="admin-topic-stats">
        <div>
          <span>Approved updates</span>
          <strong>{topics.length}</strong>
        </div>
        <div>
          <span>Topic/month buckets</span>
          <strong>{groupedTopics.length}</strong>
        </div>
      </div>

      {loading ? (
        <div className="admin-empty-state">Loading Events/Topics...</div>
      ) : groupedTopics.length ? (
        <div className="admin-topic-list">
          {groupedTopics.map((group) => (
            <section className="admin-topic-group" key={`${group.cycle}-${group.topicLabel}`}>
              <div className="admin-topic-group-heading">
                <div>
                  <strong>{group.topicLabel}</strong>
                  <span>{displayMonth(group.cycle)}</span>
                </div>
                <span>
                  {group.items.length} update{group.items.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="admin-topic-items">
                {group.items.map((topic) => (
                  <article className="admin-topic-item" key={topic.topic_update_id}>
                    <div className="admin-topic-item-copy">
                      <strong>{topic.title}</strong>
                      <div dangerouslySetInnerHTML={{ __html: topic.summary }} />
                    </div>
                    <span className="knowledge-ready-pill">{displayStatus(topic.status)}</span>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="admin-empty-state">No Events/Topics approved yet.</div>
      )}
    </div>
  );
}

function groupTopics(topics: AdminTopicUpdate[]) {
  const groups = new Map<
    string,
    { topicLabel: string; cycle: string; items: AdminTopicUpdate[] }
  >();
  for (const topic of topics) {
    const key = `${topic.cycle}:${topic.topic_label}`;
    const group = groups.get(key) ?? {
      topicLabel: topic.topic_label,
      cycle: topic.cycle,
      items: [],
    };
    group.items.push(topic);
    groups.set(key, group);
  }
  return Array.from(groups.values()).sort((left, right) => {
    if (left.cycle !== right.cycle) {
      return right.cycle.localeCompare(left.cycle);
    }
    return left.topicLabel.localeCompare(right.topicLabel);
  });
}

function displayMonth(value: string) {
  const [year, month] = value.slice(0, 7).split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return new Intl.DateTimeFormat("en", { month: "short", year: "numeric" }).format(date);
}

function displayStatus(value: string) {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}
