import { createAppAuth } from "@octokit/auth-app";
import { Octokit } from "@octokit/rest";
import type { FileChange } from "@codelens/analyzers";

export async function createAppOctokit(owner: string): Promise<Octokit> {
  const appId = process.env.GITHUB_APP_ID;
  const privateKey = process.env.GITHUB_PRIVATE_KEY?.replace(/\\n/g, "\n");

  if (!appId || !privateKey) {
    throw new Error("GITHUB_APP_ID and GITHUB_PRIVATE_KEY required");
  }

  const auth = createAppAuth({ appId, privateKey });

  let installationId = process.env.GITHUB_INSTALLATION_ID
    ? Number(process.env.GITHUB_INSTALLATION_ID)
    : undefined;

  if (!installationId) {
    const octokit = new Octokit({ authStrategy: createAppAuth, auth: { appId, privateKey } });
    const { data } = await octokit.rest.apps.getRepoInstallation({ owner, repo: "codelens-demo" }).catch(async () => {
      const installations = await octokit.rest.apps.listInstallations();
      const match = installations.data.find((i) => i.account && "login" in i.account && i.account.login === owner);
      if (!match) throw new Error(`No GitHub App installation found for ${owner}`);
      return { data: match };
    });
    installationId = data.id;
  }

  const installationAuth = await auth({ type: "installation", installationId });
  return new Octokit({ auth: installationAuth.token });
}

export async function fetchPullRequestFiles(
  octokit: Octokit,
  owner: string,
  repo: string,
  pullNumber: number
): Promise<FileChange[]> {
  const { data } = await octokit.rest.pulls.listFiles({
    owner,
    repo,
    pull_number: pullNumber,
    per_page: 100,
  });

  return data.map((f) => ({
    filename: f.filename,
    status: f.status as FileChange["status"],
    additions: f.additions,
    deletions: f.deletions,
    patch: f.patch,
  }));
}
