"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getLTIContext } from "@/lib/lti";
import { getLearnerId } from "@/lib/learner";
import { lttFetch } from "@/lib/api";

interface LTIDebugData {
  launch_id: string;
  data: {
    sub: string;
    iss: string;
    email: string | null;
    name: string | null;
    learner_id: string;
    project_id: string;
    workspace_type: string;
    roles: string[];
    context: Record<string, unknown>;
    resource_link: Record<string, unknown>;
    tool_platform: Record<string, unknown>;
    ags: Record<string, unknown>;
    custom: Record<string, unknown>;
    all_keys: string[];
  };
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2 border-b border-border pb-1">
        {title}
      </h2>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-4 py-1 text-sm">
      <span className="text-muted-foreground w-40 shrink-0">{label}</span>
      <span className="font-mono break-all">{value ?? <span className="text-muted-foreground italic">null</span>}</span>
    </div>
  );
}

export default function DebugPage() {
  const [ltiCtx, setLtiCtx] = useState<ReturnType<typeof getLTIContext>>(null);
  const [cookieLearnerId, setCookieLearnerId] = useState<string | null>(null);
  const [serverData, setServerData] = useState<LTIDebugData | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLtiCtx(getLTIContext());
    setCookieLearnerId(getLearnerId());
  }, []);

  async function fetchServerData() {
    setLoading(true);
    setServerError(null);
    try {
      const res = await lttFetch("/lti/debug/context");
      if (!res.ok) {
        setServerError(`HTTP ${res.status}`);
        return;
      }
      const json = await res.json();
      if (json.error) {
        setServerError(json.error);
      } else {
        setServerData(json);
      }
    } catch (e) {
      setServerError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (ltiCtx?.launchId) fetchServerData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ltiCtx?.launchId]);

  return (
    <div className="min-h-screen bg-background text-foreground p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-1" /> Back
            </Button>
          </Link>
          <h1 className="text-lg font-semibold">LTI Debug</h1>
        </div>
        <Button variant="outline" size="sm" onClick={fetchServerData} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-1 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <Section title="Client — sessionStorage LTI Context">
        {ltiCtx ? (
          <>
            <Row label="isLTI" value={String(ltiCtx.isLTI)} />
            <Row label="launchId" value={ltiCtx.launchId} />
            <Row label="learnerId (LTT)" value={ltiCtx.learnerId} />
            <Row label="projectId" value={ltiCtx.projectId} />
            <Row label="workspaceType" value={ltiCtx.workspaceType} />
          </>
        ) : (
          <p className="text-sm text-muted-foreground italic">No LTI context in sessionStorage (not an LTI session, or context was never stored)</p>
        )}
      </Section>

      <Section title="Client — Cookie Learner ID (standalone fallback)">
        <Row label="ltt_learner_id" value={cookieLearnerId ?? "not set"} />
      </Section>

      <Section title="Server — Full LTI Launch Data (from Redis)">
        {serverError && (
          <p className="text-sm text-destructive font-mono">{serverError}</p>
        )}
        {serverData ? (
          <>
            <Row label="launch_id" value={serverData.launch_id} />
            <Row label="sub (OpenEdX)" value={serverData.data.sub} />
            <Row label="iss" value={serverData.data.iss} />
            <Row label="email" value={serverData.data.email} />
            <Row label="name" value={serverData.data.name} />
            <Row label="learner_id (LTT)" value={serverData.data.learner_id} />
            <Row label="project_id" value={serverData.data.project_id} />
            <Row label="workspace_type" value={serverData.data.workspace_type} />
            <Row label="roles" value={serverData.data.roles.map(r => r.split("#").pop()).join(", ")} />
            <Row label="context.id" value={String(serverData.data.context.id ?? "")} />
            <Row label="context.title" value={String(serverData.data.context.title ?? "")} />
            <Row label="resource_link.id" value={String(serverData.data.resource_link.id ?? "")} />
            <Row label="platform.name" value={String(serverData.data.tool_platform.name ?? "")} />
            <Row label="platform.guid" value={String(serverData.data.tool_platform.guid ?? "")} />
            <Row label="AGS endpoint" value={String(serverData.data.ags.lineitems ?? "")} />
            <Row label="AGS scopes" value={(serverData.data.ags.scope as string[] | undefined)?.map(s => s.split("/").pop()).join(", ")} />
            <Row label="custom" value={JSON.stringify(serverData.data.custom)} />
            <div className="mt-3">
              <p className="text-xs text-muted-foreground mb-1">All JWT claim keys:</p>
              <pre className="text-xs font-mono bg-muted p-2 rounded overflow-auto">
                {serverData.data.all_keys.join("\n")}
              </pre>
            </div>
          </>
        ) : !serverError && (
          <p className="text-sm text-muted-foreground italic">
            {ltiCtx ? "Loading..." : "No LTI session active"}
          </p>
        )}
      </Section>

      <Section title="User ID Mapping">
        <p className="text-sm text-muted-foreground mb-2">
          LTT generates an internal <code>learner-&#123;hex8&#125;</code> ID and maps it to the
          OpenEdX <code>sub</code> UUID in the <code>lti_user_mappings</code> table. This keeps
          LTT portable across platforms.
        </p>
        {serverData && (
          <div className="font-mono text-xs bg-muted p-3 rounded">
            <div>OpenEdX sub: {serverData.data.sub}</div>
            <div className="text-yellow-400">↓ lti_user_mappings table</div>
            <div>LTT learner_id: {serverData.data.learner_id}</div>
          </div>
        )}
      </Section>
    </div>
  );
}
