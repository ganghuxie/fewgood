from pathlib import Path


WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "pages.yml"


def test_pages_workflow_uploads_in_build_and_deploys_in_dependent_job():
    source = WORKFLOW.read_text()

    build_source, deploy_source = source.split("\n  deploy:\n", maxsplit=1)

    assert "uses: actions/upload-pages-artifact@v3" in build_source
    assert "path: site/dist" in build_source
    assert "uses: actions/deploy-pages@v4" not in build_source

    assert "needs: build" in deploy_source
    assert "uses: actions/deploy-pages@v4" in deploy_source
    assert "id: deployment" in deploy_source
    assert "name: github-pages" in deploy_source
    assert "url: ${{ steps.deployment.outputs.page_url }}" in deploy_source
    assert "pages: write" in deploy_source
    assert "id-token: write" in deploy_source


def test_pages_build_checks_remain_before_upload():
    source = WORKFLOW.read_text()
    build_source = source.split("\n  deploy:\n", maxsplit=1)[0]

    for required_step in (
        "run: npm run build",
        "run: python -m ytrec.crawl_links",
        "uses: actions/configure-pages@v5",
        "uses: actions/upload-pages-artifact@v3",
    ):
        assert required_step in build_source

    assert build_source.index("run: npm run build") < build_source.index(
        "run: python -m ytrec.crawl_links"
    )
    assert build_source.index("run: python -m ytrec.crawl_links") < build_source.index(
        "uses: actions/upload-pages-artifact@v3"
    )
