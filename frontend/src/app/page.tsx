"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useBackend } from "@/components/BackendContext";
import {
  Send,
  Sparkles,
  Briefcase,
  Calendar,
  TrendingUp,
  Brain,
  Zap,
  ArrowRight,
  ArrowUpRight,
  ShieldCheck,
} from "lucide-react";
import styles from "./Dashboard.module.css";

export default function DashboardPage() {
  const { apiUrl, userId } = useBackend();
  const [userName, setUserName] = useState("John");
  const [metrics, setMetrics] = useState<any[]>([]);
  const [topJobs, setTopJobs] = useState<any[]>([]);
  const [agentActivities, setAgentActivities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const name = localStorage.getItem("userName");
    if (name) {
      setUserName(name.split(" ")[0]);
    }
  }, []);

  useEffect(() => {
    const fetchDashboardData = async () => {
      if (!userId) return;
      setLoading(true);
      try {
        const res = await fetch(`${apiUrl}/users/${userId}/dashboard`);
        if (res.ok) {
          const data = await res.json();
          
          // Map metrics data
          const mappedMetrics = [
            {
              label: "Applications Sent",
              value: data.metrics.applications_sent,
              trend: "Across all pipelines",
              trendDirection: "neutral",
              icon: Send,
              iconType: styles.primaryIcon,
            },
            {
              label: "Avg Match Rate",
              value: data.metrics.avg_match,
              trend: "Based on CV skills",
              trendDirection: "up",
              icon: Sparkles,
              iconType: styles.accentIcon,
            },
            {
              label: "Recommended Jobs",
              value: data.metrics.recommended_jobs,
              trend: "High compatibility",
              trendDirection: "neutral",
              icon: Briefcase,
              iconType: styles.secondaryIcon,
            },
            {
              label: "Interviews Booked",
              value: data.metrics.interviews_booked,
              trend: "Coaching session active",
              trendDirection: "neutral",
              icon: Calendar,
              iconType: styles.warningIcon,
            },
          ];
          setMetrics(mappedMetrics);
          setTopJobs(data.spotlight || []);

          // Map activities
          const mappedActivities = data.activities.map((act: any) => {
            let dotStyle = styles.secondary;
            if (act.dotStyle.includes("success")) dotStyle = styles.success;
            else if (act.dotStyle.includes("primary")) dotStyle = styles.primary;
            else if (act.dotStyle.includes("accent")) dotStyle = styles.accent;
            return {
              ...act,
              dotStyle,
            };
          });
          setAgentActivities(mappedActivities);
        }
      } catch (err) {
        console.warn("Failed to fetch dashboard statistics:", err);
      }
      setLoading(false);
    };

    fetchDashboardData();
  }, [apiUrl, userId]);

  return (
    <div className={styles.dashboardContainer}>
      {/* Welcome Section */}
      <header className={styles.welcomeSection}>
        <h1 className="animate-fade-in">Welcome Back, {userName}</h1>
        <p className={styles.welcomeSubtitle}>
          Your AI Agents are active. They have analyzed 142 job openings today and optimized 1 application.
        </p>
      </header>

      {/* Metrics Section */}
      <section className={styles.metricsGrid}>
        {metrics.map((m, idx) => {
          const Icon = m.icon;
          return (
            <div key={idx} className="glass glass-hover metric-card-animation" style={{ animationDelay: `${idx * 0.1}s` }}>
              <div className={styles.metricCard}>
                <div className={styles.metricContent}>
                  <span className={styles.metricLabel}>{m.label}</span>
                  <span className={styles.metricValue}>{m.value}</span>
                  <span className={styles.metricMeta}>
                    {m.trendDirection === "up" ? (
                      <TrendingUp size={12} className={styles.trendUp} />
                    ) : null}
                    <span style={{ color: m.trendDirection === "up" ? "var(--success)" : "var(--text-muted)" }}>
                      {m.trend}
                    </span>
                  </span>
                </div>
                <div className={`${styles.metricIconWrapper} ${m.iconType}`}>
                  <Icon size={20} />
                </div>
              </div>
            </div>
          );
        })}
      </section>

      {/* Main Grid Content */}
      <div className={styles.dashboardLayout}>
        {/* Left Side: Top Job Matches */}
        <section className="glass panel animate-slide-up" style={{ animationDelay: "0.2s" }}>
          <div className={styles.panelTitle}>
            <Brain size={18} style={{ color: "var(--primary)" }} />
            <span>AI Spotlight Recommendations</span>
          </div>
          
          <div className={styles.jobGrid}>
            {topJobs.map((job) => (
              <div key={job.id} className={`${styles.jobCard} glass-hover`} style={{ background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--border-color)", borderRadius: 12 }}>
                <div className={styles.jobInfo}>
                  <div className={styles.companyLogo}>{job.logo}</div>
                  <div className={styles.jobMeta}>
                    <span className={styles.jobTitle}>{job.title}</span>
                    <span className={styles.companyName}>
                      {job.company} • {job.location} • {job.salary}
                    </span>
                    <div className={styles.jobTags}>
                      {job.tags.map((t: string, i: number) => (
                        <span key={i} className={styles.tag}>
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className={styles.matchBadge}>
                  <div className={`${styles.scoreCircle} ${job.match >= 90 ? styles.high : ""}`}>
                    {job.match}%
                  </div>
                  <Link href={`/jobs?id=${job.id}`}>
                    <button className={styles.applyBtn}>
                      Optimize & Apply
                    </button>
                  </Link>
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 20 }}>
            <Link href="/jobs" style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--primary)", fontWeight: 600 }}>
              <span>Browse All Recommended Jobs</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </section>

        {/* Right Side: Agent Activities & Actions */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Quick Mock Interview Box */}
          <section className="glass panel animate-slide-up" style={{ animationDelay: "0.3s", padding: 20, background: "linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(168, 85, 247, 0.05) 100%)", borderColor: "rgba(99, 102, 241, 0.2)" }}>
            <div className={styles.panelTitle} style={{ marginBottom: 12 }}>
              <Zap size={18} style={{ color: "var(--accent)" }} />
              <span>Next Action Required</span>
            </div>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: 16 }}>
              You have a mock interview scheduled for <strong>Senior React Developer</strong> role at Vercel. Try a 10-minute prep session.
            </p>
            <Link href="/interview">
              <button 
                className={styles.applyBtn} 
                style={{ 
                  background: "linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%)", 
                  width: "100%", 
                  display: "flex", 
                  alignItems: "center", 
                  justifyContent: "center", 
                  gap: 8,
                  padding: "10px 16px"
                }}
              >
                <span>Start Mock Interview</span>
                <ArrowUpRight size={14} />
              </button>
            </Link>
          </section>

          {/* Agent Activity Timeline */}
          <section className="glass panel animate-slide-up" style={{ animationDelay: "0.4s", padding: 20 }}>
            <div className={styles.panelTitle} style={{ marginBottom: 16 }}>
              <ShieldCheck size={18} style={{ color: "var(--secondary)" }} />
              <span>Multi-Agent Activity Log</span>
            </div>
            
            <div className={styles.timeline}>
              {agentActivities.map((act, i) => (
                <div key={i} className={styles.timelineItem}>
                  <div className={`${styles.timelineDot} ${act.dotStyle}`}></div>
                  <div className={styles.timelineTime}>{act.time}</div>
                  <div className={styles.timelineTitle}>{act.agent}</div>
                  <div className={`${styles.timelineDesc} ${styles.timelineCard}`}>
                    <strong>{act.title}</strong>: {act.desc}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
