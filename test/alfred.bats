setup_file() {
    echo "# ---Starting alfred bash test suite" >&3


    echo "* ---.......setup token file" >&3
    touch test/token.sesh
}

setup() {
    echo "# --Starting alfred test" >&3

    echo "* --.......load support submodules" >&3
    load '../opt/bats-support/load'
    load '../opt/bats-assert/load'

    echo "# --.......link token file" >&3
    token_file=test/token.sesh
}

# @test "can init alfred" {
#     run ./al init
# }

# @test "can install alfred" {
#     run ./al install
# }

# @test "can dev with alfred" {
#     run ./al dev --build
# }

# @test "# -can get stage" {
#     run curl https://stage.alfred.quaternion.media
#     assert_output --partial '<html>'
# }

# @test "# -can get prod" {
#     run curl https://alfred.quaternion.media
# }

register() {
    curl -sH "Content-Type: application/json" \
        -X POST \
        -d '{"email":"your@email.com","password":"yourpassword","first_name":"yourname"}' \
        $BATS_baseURL/auth/register

}

@test "# -register" {
    run register
    # assert_output --regexp '*(REGISTER_USER_ALREADY_EXISTS)?*'
    assert_output --partial "{"
}

registeredLogin() {
    curl -s -X POST \
        -F "username=your@email.com" \
        -F "password=yourpassword" \
        $BATS_baseURL/auth/jwt/login | jq -r '.access_token' | tee test/token.sesh
}

@test "# -regestered login" {
    run registeredLogin 
    assert_output --partial "."
    assert_equal $(echo $output | wc -m) "210"
}

previewFrame() {
    token=$(<test/token.sesh)
    curl -s -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d $(<test/data.json) \
        $BATS_baseURL/otto/preview?t=1 | tee test/rUrl
}

@test "# -preview frame" {

    echo '{"clips":[{"type":"template","name":"title","data":{"text":"asdf"}}]}' > test/data.json
    # validate edl w api?

    run previewFrame
    assert_output --partial ".png"
}

teardown() {
    echo "# --Ending alfred test" >&3

}

teardown_file() {
    echo "* --.......cleaning up token" >&3
    rm test/token.sesh

    echo "# ---Ending alfred bats test suite"
}
