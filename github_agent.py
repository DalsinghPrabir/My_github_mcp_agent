import asyncio
import json
import os
import streamlit as st
import requests
from textwrap import dedent
from agno.agent import Agent
from agno.run.agent import RunOutput

st.set_page_config(page_title="🐙 GitHub MCP Agent", page_icon="🐙", layout="wide")

st.markdown("<h1 class='main-header'>🐙 GitHub MCP Agent</h1>", unsafe_allow_html=True)
st.markdown("Explore GitHub repositories with natural language using the Model Context Protocol")

with st.sidebar:
    st.header("🔑 Authentication")
    
    openai_key = st.text_input("OpenAI API Key", type="password",
                              help="Required for the AI agent to interpret queries and format results")
    if openai_key:
        os.environ["OPENAI_API_KEY"] = openai_key
    
    github_token = st.text_input("GitHub Token", type="password", 
                                help="Create a token with repo scope at github.com/settings/tokens")
    if github_token:
        os.environ["GITHUB_TOKEN"] = github_token
    
    st.markdown("---")
    st.markdown("### Example Queries")
    
    st.markdown("**Issues**")
    st.markdown("- Show me issues by label")
    st.markdown("- What issues are being actively discussed?")
    
    st.markdown("**Pull Requests**")
    st.markdown("- What PRs need review?")
    st.markdown("- Show me recent merged PRs")
    
    st.markdown("**Repository**")
    st.markdown("- Show repository health metrics")
    st.markdown("- Show repository activity patterns")
    
    st.markdown("---")
    st.caption("Note: Always specify the repository in your query if not already selected in the main input.")

col1, col2 = st.columns([3, 1])
with col1:
    repo = st.text_input("Repository", value="DalsinghPrabir/RAG-Assistant", help="Format: owner/repo")
with col2:
    query_type = st.selectbox("Query Type", [
        "Issues", "Pull Requests", "Repository Activity", "Custom"
    ])

if query_type == "Issues":
    query_template = f"Find issues labeled as bugs in {repo}"
elif query_type == "Pull Requests":
    query_template = f"Show me recent merged PRs in {repo}"
elif query_type == "Repository Activity":
    query_template = f"Analyze code quality trends in {repo}"
else:
    query_template = ""

query = st.text_area("Your Query", value=query_template, 
                     placeholder="What would you like to know about this repository?")

async def run_github_agent(message):
    if not os.getenv("GITHUB_TOKEN"):
        return "Error: GitHub token not provided"
    
    if not os.getenv("OPENAI_API_KEY"):
        return "Error: OpenAI API key not provided"

    try:
        agent = Agent(
            tools=[
                get_repository,
                search_issues,
                list_pull_requests,
                list_repository_activity,
            ],
            instructions=dedent("""\
                You are a GitHub assistant. Help users explore repositories and their activity.
                Use the GitHub tools to get current data before answering.
                - Provide organized, concise insights about the repository
                - Focus on facts and data from the GitHub API
                - Use markdown formatting for better readability
                - Present numerical data in tables when appropriate
                - Include links to relevant GitHub pages when helpful
            """),
            markdown=True,
        )

        response: RunOutput = await asyncio.wait_for(agent.arun(message), timeout=120.0)
        return response.content
                
    except asyncio.TimeoutError:
        return "Error: Request timed out after 120 seconds"
    except Exception as e:
        error_message = str(e)
        if "insufficient_quota" in error_message or "credit_balance_exhausted" in error_message:
            return (
                "OpenAI has no credits remaining for this API key. "
                "Add billing credits at https://platform.openai.com/settings/organization/billing/ "
                "or use an API key from an account with available credits."
            )
        return f"Error: {error_message}"


def _github_request(endpoint, params=None):
    """Make an authenticated, read-only request to the GitHub REST API."""
    response = requests.get(
        f"https://api.github.com{endpoint}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_repository(repository: str):
    """Get metadata and health metrics for an owner/repository."""
    return json.dumps(_github_request(f"/repos/{repository}"), indent=2)


def search_issues(repository: str, search: str = "", state: str = "open", limit: int = 20):
    """Find issues in a repository, optionally filtered by a GitHub search term."""
    query = f"repo:{repository} is:issue state:{state}"
    if search:
        query += f" {search}"
    result = _github_request("/search/issues", {"q": query, "per_page": min(limit, 100)})
    return json.dumps(result, indent=2)


def list_pull_requests(repository: str, state: str = "open", limit: int = 20):
    """List pull requests for an owner/repository."""
    result = _github_request(
        f"/repos/{repository}/pulls",
        {"state": state, "per_page": min(limit, 100), "sort": "updated", "direction": "desc"},
    )
    return json.dumps(result, indent=2)


def list_repository_activity(repository: str, limit: int = 20):
    """List recent commits for an owner/repository as a simple activity signal."""
    result = _github_request(f"/repos/{repository}/commits", {"per_page": min(limit, 100)})
    return json.dumps(result, indent=2)

if st.button("🚀 Run Query", type="primary", use_container_width=True):
    if not openai_key:
        st.error("Please enter your OpenAI API key in the sidebar")
    elif not github_token:
        st.error("Please enter your GitHub token in the sidebar")
    elif not query:
        st.error("Please enter a query")
    else:
        with st.spinner("Analyzing GitHub repository..."):
            if repo and repo not in query:
                full_query = f"{query} in {repo}"
            else:
                full_query = query
                
            result = asyncio.run(run_github_agent(full_query))
        
        st.markdown("### Results")
        st.markdown(result)

if 'result' not in locals():
    st.markdown(
        """<div class='info-box'>
        <h4>How to use this app:</h4>
        <ol>
            <li>Enter your <strong>OpenAI API key</strong> in the sidebar (powers the AI agent)</li>
            <li>Enter your <strong>GitHub token</strong> in the sidebar</li>
            <li>Specify a repository (e.g., DalsinghPrabir/RAG-Assistant)</li>
            <li>Select a query type or write your own</li>
            <li>Click 'Run Query' to see results</li>
        </ol>
        <p><strong>How it works:</strong></p>
        <ul>
            <li>Uses the GitHub REST API directly for current repository data</li>
            <li>AI Agent (powered by OpenAI) interprets your queries and calls appropriate GitHub APIs</li>
            <li>Results are formatted in readable markdown with insights and links</li>
            <li>Queries work best when focused on specific aspects like issues, PRs, or repository info</li>
        </ul>
        </div>""", 
        unsafe_allow_html=True
    )
