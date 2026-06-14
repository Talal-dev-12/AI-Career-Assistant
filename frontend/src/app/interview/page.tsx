"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  MessageSquareCode,
  Video,
  Mic,
  MicOff,
  Send,
  Play,
  Award,
  BookOpen,
  RefreshCcw,
  ChevronRight,
} from "lucide-react";
import styles from "./Interview.module.css";
import { useBackend } from "@/components/BackendContext";

interface QAFeedback {
  question: string;
  answer: string;
  score: number;
  strength: string;
  improvement: string;
}

interface MABDQuestionFeedback {
  question: string;
  response: string;
  score: number;
  strengths: string;
  improvement_suggestions: string;
}

interface TalhaTurnFeedback {
  question: string;
  answer: string;
  score?: number;
  feedback?: string;
}

export default function InterviewPage() {
  const { apiUrl, userId } = useBackend();

  // Simulator modes: 'setup' | 'active' | 'feedback'
  const [mode, setMode] = useState<"setup" | "active" | "feedback">("setup");
  const [prepMethod, setPrepMethod] = useState<"talha" | "mabd">("talha");
  const [targetJob, setTargetJob] = useState("");
  const [jobs, setJobs] = useState<{ id: string; title: string; company: string }[]>([]);

  // Active session states
  const [sessionId, setSessionId] = useState<string | number | null>(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [candidateTranscript, setCandidateTranscript] = useState("");
  const [loading, setLoading] = useState(false);

  const [chatLog, setChatLog] = useState<{ sender: "ai" | "user"; text: string }[]>([]);
  const [activeQuestions, setActiveQuestions] = useState<string[]>([]);
  const [evaluationScore, setEvaluationScore] = useState(85);
  const [qaFeedbacks, setQaFeedbacks] = useState<QAFeedback[]>([]);
  const [overallFeedback, setOverallFeedback] = useState("");

  const simulatedAnswers = [
    "In Next.js, static rendering pre-renders routes at build time, making them extremely fast and cacheable. Dynamic rendering renders routes at request time, which is necessary when pages need user-specific data. To force dynamic rendering, we can export const dynamic = 'force-dynamic' or use dynamic functions like cookies() or headers() inside the component.",
    "To optimize bundle sizes, I would use dynamic imports via next/dynamic to lazy load the heavy charts so they are only downloaded on the client when needed. I would also run @next/bundle-analyzer to audit packages and prune unused dependencies, or configure tree-shaking in imports.",
    "FastAPI is built on Starlette and Pydantic, enabling automatic validation and high-speed execution. System scaling involves vertical/horizontal options, load balancing, database connection pools, and utilizing a Redis cache layer for read-heavy operations.",
    "I design databases by first normalizing tables to 3NF, establishing indexes on foreign key columns and frequently queried fields, and conducting performance tests under high concurrency.",
    "I had to learn Docker containerization for a deployment project. I went through Docker docs, constructed sample containers, and built multi-stage deployment workflows to reduce image size by 50%."
  ];

  // Fetch jobs dynamically for MABD method
  React.useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await fetch(`${apiUrl}/jobs`);
        if (res.ok) {
          const data = await res.json();
          setJobs(data);
          if (data.length > 0) {
            setTargetJob(data[0].id);
          }
        }
      } catch (err) {
        console.warn("Failed to fetch jobs for interview setup:", err);
      }
    };
    fetchJobs();
  }, [apiUrl]);

  // Handlers
  const startInterview = async () => {
    setLoading(true);
    setChatLog([]);
    setCandidateTranscript("");
    
    try {
      if (prepMethod === "mabd") {
        const res = await fetch(`${apiUrl}/interview/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId || "",
            job_id: targetJob,
          }),
        });

        if (res.ok) {
          const data = await res.json();
          setSessionId(data.id);
          setActiveQuestions(data.question_set || []);
          setQuestionIndex(0);
          setChatLog([
            {
              sender: "ai",
              text: data.question_set?.[0] || "Could you tell me about your technical background?",
            },
          ]);
          setMode("active");
        }
      } else {
        // Talha uses role ("software engineer" by default)
        const res = await fetch(`${apiUrl}/users/${userId}/interview/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            role: "software engineer",
          }),
        });

        if (res.ok) {
          const data = await res.json();
          setSessionId(data.session_id);
          setQuestionIndex(0);
          setChatLog([
            {
              sender: "ai",
              text: data.question,
            },
          ]);
          setActiveQuestions([data.question]);
          setMode("active");
        }
      }
    } catch (err) {
      console.error("Failed to start mock interview:", err);
      alert("Failed to start interview. Make sure the backend is running!");
    }
    setLoading(false);
  };

  const handleStartSpeaking = () => {
    setIsSpeaking(true);
    // Simulate candidate speaking and speech-to-text typing out
    setTimeout(() => {
      setCandidateTranscript(simulatedAnswers[questionIndex % simulatedAnswers.length]);
      setIsSpeaking(false);
    }, 2000);
  };

  const handleSubmitAnswer = async () => {
    if (!candidateTranscript) {
      alert("Please record or write your answer first!");
      return;
    }
    setLoading(true);

    const currentAnswer = candidateTranscript;
    setChatLog((prev) => [...prev, { sender: "user" as const, text: currentAnswer }]);
    setCandidateTranscript("");

    try {
      if (prepMethod === "mabd") {
        const res = await fetch(`${apiUrl}/interview/${sessionId}/answer`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question_index: questionIndex,
            answer: currentAnswer,
          }),
        });

        if (res.ok) {
          await res.json();
          const nextIndex = questionIndex + 1;
          
          if (nextIndex < activeQuestions.length) {
            setQuestionIndex(nextIndex);
            setTimeout(() => {
              setChatLog((prev) => [...prev, { sender: "ai", text: activeQuestions[nextIndex] }]);
            }, 1000);
          } else {
            // Evaluated session
            const evalRes = await fetch(`${apiUrl}/interview/${sessionId}/evaluate`, {
              method: "POST",
            });
            if (evalRes.ok) {
              const evalData = await evalRes.json();
              setEvaluationScore(evalData.score || 85);
              setOverallFeedback(evalData.feedback?.overall_feedback || "The candidate shows good command of core technologies.");
              
              const mappedQA: QAFeedback[] = (evalData.feedback?.questions_feedback || []).map((qa: MABDQuestionFeedback) => ({
                question: qa.question,
                answer: qa.response,
                score: qa.score,
                strength: qa.strengths,
                improvement: qa.improvement_suggestions,
              }));
              setQaFeedbacks(mappedQA);
              
              setTimeout(() => {
                setMode("feedback");
              }, 1500);
            }
          }
        }
      } else {
        const res = await fetch(`${apiUrl}/interview/${sessionId}/answer`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            answer: currentAnswer,
          }),
        });

        if (res.ok) {
          const data = await res.json();
          if (data.next_question) {
            setQuestionIndex((prev) => prev + 1);
            setActiveQuestions((prev) => [...prev, data.next_question]);
            setTimeout(() => {
              setChatLog((prev) => [...prev, { sender: "ai", text: data.next_question }]);
            }, 1000);
          }

          if (data.completed) {
            const transcriptRes = await fetch(`${apiUrl}/interview/${sessionId}`);
            if (transcriptRes.ok) {
              const transcriptData = await transcriptRes.json();
              setEvaluationScore(Math.round((transcriptData.average_score || 8.5) * 10)); // map 1-10 to 1-100
              setOverallFeedback("The interview session has been processed successfully. Detailed responses are graded below.");
              
              const mappedQA: QAFeedback[] = (transcriptData.turns || []).map((turn: TalhaTurnFeedback) => ({
                question: turn.question,
                answer: turn.answer,
                score: Math.round((turn.score || 8.0) * 10),
                strength: turn.feedback || "Solid response with relevant keywords.",
                improvement: "Enhance details with structural metrics.",
              }));
              setQaFeedbacks(mappedQA);

              setTimeout(() => {
                setMode("feedback");
              }, 1500);
            }
          }
        }
      }
    } catch (err) {
      console.error("Failed to submit interview answer:", err);
    }
    setLoading(false);
  };

  return (
    <div className={styles.container}>
      {/* Header */}
      <header className={styles.header}>
        <h1>AI Interview Prep Center</h1>
        <p>
          Practice for target roles with our interactive mock interviewer. Receive instant scores and suggestions on communication clarity.
        </p>
      </header>

      {/* Setup screen */}
      {mode === "setup" && (
        <div className={`${styles.setupCard} glass`}>
          <div className={styles.setupIcon}>
            <MessageSquareCode size={32} />
          </div>
          <h2 className={styles.setupTitle}>Configure Practice Session</h2>
          <p className={styles.setupDesc}>
            Select your preferred preparation method and target position. The AI Agent will generate custom panel simulations to evaluate your responses.
          </p>

          {/* Prep Method Selection cards */}
          <div style={{ display: "flex", gap: 16, width: "100%", marginBottom: 20 }}>
            <div 
              onClick={() => setPrepMethod("talha")}
              style={{
                flex: 1,
                padding: 16,
                borderRadius: 12,
                border: prepMethod === "talha" ? "2px solid var(--primary)" : "1px solid var(--border-color)",
                background: prepMethod === "talha" ? "rgba(99, 102, 241, 0.05)" : "rgba(255,255,255,0.01)",
                cursor: "pointer",
                textAlign: "left"
              }}
            >
              <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 6, color: prepMethod === "talha" ? "var(--primary)" : "inherit" }}>Role-based Simulator (Talha)</h3>
              <p style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.4 }}>
                Engage in conversational Q&A sessions. Receive grading and coaching feedback after each turn.
              </p>
            </div>
            
            <div 
              onClick={() => setPrepMethod("mabd")}
              style={{
                flex: 1,
                padding: 16,
                borderRadius: 12,
                border: prepMethod === "mabd" ? "2px solid var(--secondary)" : "1px solid var(--border-color)",
                background: prepMethod === "mabd" ? "rgba(20, 184, 166, 0.05)" : "rgba(255,255,255,0.01)",
                cursor: "pointer",
                textAlign: "left"
              }}
            >
              <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 6, color: prepMethod === "mabd" ? "var(--secondary)" : "inherit" }}>Job-focused Evaluator (MABD)</h3>
              <p style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.4 }}>
                Complete a structured panel of 5 pre-generated questions. Get bulk performance reports at the end.
              </p>
            </div>
          </div>

          {prepMethod === "mabd" && (
            <div className={styles.selectBox} style={{ textAlign: "left", marginBottom: 20 }}>
              <span style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>
                SELECT TARGET POSITION
              </span>
              <select
                style={{ background: "transparent", color: "inherit", width: "100%", fontSize: 14, cursor: "pointer", border: "none", outline: "none" }}
                value={targetJob}
                onChange={(e) => setTargetJob(e.target.value)}
              >
                {jobs.map((job) => (
                  <option key={job.id} value={job.id} style={{ background: "var(--bg-dark)" }}>
                    {job.company} - {job.title}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button className={styles.startBtn} onClick={startInterview} disabled={loading}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              {loading ? (
                <span className="status-dot active" style={{ width: 8, height: 8 }}></span>
              ) : (
                <Play size={16} fill="white" />
              )}
              <span>{loading ? "Launching Simulator..." : "Launch Mock Interview Simulator"}</span>
            </div>
          </button>
        </div>
      )}

      {/* Active Simulator Screen */}
      {mode === "active" && (
        <div className={styles.portalGrid}>
          {/* Left panel: Simulated Video feeds */}
          <div className={`${styles.videoFeedCard} glass`}>
            <div className={styles.panelTitle}>
              <Video size={18} style={{ color: "var(--accent)" }} />
              <span>Interactive Simulator Feeds</span>
            </div>

            {/* Simulated Interviewer Camera */}
            <div className={styles.videoPlaceholder}>
              <div className={styles.speakingIndicator}>
                <span className="status-dot active"></span>
                <span>Interviewer: AI Agent (speaking)</span>
              </div>
              <div className={styles.waveContainer}>
                <div className={styles.waveBar}></div>
                <div className={styles.waveBar}></div>
                <div className={styles.waveBar}></div>
                <div className={styles.waveBar}></div>
                <div className={styles.waveBar}></div>
                <div className={styles.waveBar}></div>
                <div className={styles.waveBar}></div>
              </div>
              <span style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600, marginTop: 12 }}>
                AI Core Platform Interviewer
              </span>
            </div>

            {/* Controls */}
            <div className={styles.controlsRow}>
              <button
                className={`${styles.micBtn} ${isSpeaking ? styles.micBtnActive : ""}`}
                onClick={handleStartSpeaking}
                disabled={loading}
              >
                {isSpeaking ? (
                  <>
                    <MicOff size={16} />
                    <span>Listening voice...</span>
                  </>
                ) : (
                  <>
                    <Mic size={16} />
                    <span>Simulate Speaking (Answer)</span>
                  </>
                )}
              </button>
              <button className={styles.submitBtn} onClick={handleSubmitAnswer} disabled={loading}>
                <Send size={16} />
                <span>{loading ? "Analyzing Answer..." : "Submit Answer"}</span>
              </button>
            </div>

            {/* Live speech transcription text-area */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                Live Speech-to-Text Transcription Output
              </span>
              <textarea
                className="glass"
                style={{
                  width: "100%",
                  minHeight: 80,
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid var(--border-color)",
                  borderRadius: 8,
                  padding: 12,
                  color: "var(--text-primary)",
                  fontSize: 13,
                  resize: "none",
                }}
                value={candidateTranscript}
                onChange={(e) => setCandidateTranscript(e.target.value)}
                placeholder="Click 'Simulate Speaking' or type your answer directly here..."
              />
            </div>
          </div>

          {/* Right Panel: Chat log feed */}
          <div className={`${styles.chatCard} glass`}>
            <div className={styles.panelTitle} style={{ borderBottom: "1px solid var(--border-color)", paddingBottom: 12 }}>
              <span>Live Interview Log</span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", flex: 1, overflowY: "auto", gap: 16 }}>
              {chatLog.map((chat, idx) => (
                <div
                  key={idx}
                  className={`${styles.messageBubble} ${
                    chat.sender === "ai" ? styles.interviewerMsg : styles.candidateMsg
                  }`}
                >
                  <strong style={{ display: "block", fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>
                    {chat.sender === "ai" ? "AI INTERVIEWER" : "YOU (CANDIDATE)"}
                  </strong>
                  <span>{chat.text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Feedback Review Screen */}
      {mode === "feedback" && (
        <div className={`${styles.feedbackCard} glass`}>
          <div className={styles.feedbackTitle}>
            <Award size={22} style={{ color: "var(--secondary)" }} />
            <span>AI Mock Performance Report</span>
          </div>

          {/* Overall grade and metrics */}
          <div className={styles.scoreRow}>
            <div className={styles.scoreCircle}>
              <span className={styles.scoreVal}>{evaluationScore}</span>
              <span className={styles.scoreLabel}>Score</span>
            </div>
            
            <div className={styles.sentimentCard}>
              <div>
                <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>Speech Pace</span>
                <div className={styles.sentimentVal}>122 WPM</div>
                <span style={{ fontSize: 9, color: "var(--success)" }}>Optimal</span>
              </div>
              <div>
                <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>Confidence Index</span>
                <div className={styles.sentimentVal}>High</div>
                <span style={{ fontSize: 9, color: "var(--success)" }}>Strong tone</span>
              </div>
              <div>
                <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>Grammar Rating</span>
                <div className={styles.sentimentVal}>Excellent</div>
                <span style={{ fontSize: 9, color: "var(--success)" }}>Few fillers</span>
              </div>
            </div>
          </div>

          {overallFeedback && (
            <div style={{ marginTop: 20, padding: 16, background: "rgba(255,255,255,0.02)", border: "1px solid var(--border-color)", borderRadius: 12 }}>
              <strong style={{ display: "block", fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>
                AI Coach Assessment
              </strong>
              <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                {overallFeedback}
              </p>
            </div>
          )}

          {/* Question breakdown list */}
          <div className={styles.analysisSection}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)" }}>
              Detailed Question-by-Question Grading
            </h3>

            {qaFeedbacks.map((qa, idx) => (
              <div key={idx} className={styles.analysisQuestionBlock}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: "var(--primary)" }}>
                    Question {idx + 1} ({qa.score}% Match Score)
                  </span>
                </div>
                <p style={{ fontSize: 13, color: "var(--text-primary)", fontWeight: 600, marginBottom: 6 }}>
                  Q: {qa.question}
                </p>
                <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12, fontStyle: "italic" }}>
                  Your Answer: &ldquo;{qa.answer}&rdquo;
                </p>

                <ul className={styles.bulletList}>
                  <li>
                    <strong style={{ color: "var(--success)" }}>Core Strength:</strong> {qa.strength}
                  </li>
                  <li>
                    <strong style={{ color: "var(--warning)" }}>Suggested Refinement:</strong> {qa.improvement}
                  </li>
                </ul>
              </div>
            ))}
          </div>

          {/* Action Footer */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--border-color)", paddingTop: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--text-secondary)" }}>
              <BookOpen size={16} />
              <span>We recommend practicing the components on your roadmap next.</span>
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <Link href="/roadmap">
                <button className={styles.submitBtn}>
                  <span>View Skills Roadmap</span>
                  <ChevronRight size={14} />
                </button>
              </Link>
              <button
                className={styles.startBtn}
                style={{ width: "auto", padding: "10px 20px" }}
                onClick={() => setMode("setup")}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <RefreshCcw size={14} />
                  <span>Practice Again</span>
                </div>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
