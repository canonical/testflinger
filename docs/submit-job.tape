########################################################################
##                                                                    ##
## Must run from same `docs/` directory which must be next to `cli/`  ##
##                                                                    ##
########################################################################

Output images/submit-job.gif

Set Padding 10

Set FontSize 16
Set Width 800
Set Height 300

Set Shell "bash"
Require echo

Hide
Type "export PROMPT_COMMAND=''" Enter 0.1
Type "export TESTFLINGER_SERVER=https://testflinger-staging.canonical.com" Enter 0.1
Type "alias testflinger='cd ../cli && uv run testflinger'" Enter 0.1
Type "clear" Enter 0.1
Show

Type "testflinger submit --poll ~/demo.yaml" Enter

Sleep 450

Ctrl+C
Type y Enter
Sleep 1

Ctrl+C
Sleep 1
