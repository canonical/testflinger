########################################################################
##                                                                    ##
## Must run from same `docs/` directory which must be next to `cli/`  ##
##                                                                    ##
########################################################################

Output images/submit-job.gif
Output images/submit-job.mp4

Set Padding 10

Set FontSize 16
Set Width 840
Set Height 300

Set Shell "bash"
Require echo

Hide
Type "export PROMPT_COMMAND=''" Enter 0.1
Type "export TESTFLINGER_SERVER=https://testflinger-staging.canonical.com" Enter 0.1
Type "alias testflinger='cd ../cli && uv run testflinger'" Enter 0.1
Type "clear" Enter 0.1
Show

Type "testflinger submit --poll ../docs/submit-job.demo.yaml" Enter

Sleep 450
Sleep 300
Sleep 10
