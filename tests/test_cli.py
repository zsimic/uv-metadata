def test_cli(cli):
    cli.run(cli.project_folder)
    assert cli.succeeded
    assert "uv pip show uv-metadata" in cli.logged.stderr
    assert '"uv-metadata": "uv_metadata:main"' in cli.logged.stdout
