import json
import json
import os
import time

from testflows.core import TestScenario, Name, When, Then, Given, And, main, run, Module, TE
from testflows.asserts import error
from testflows.connect import Shell

from kubectl import *
from clickhouse import *
from test_examples import *


@TestScenario
@Name("test_001. 1 node")
def test_001():
    create_and_check("configs/test-001.yaml", {"object_counts": [1,1,2]})
    
@TestScenario
@Name("test_002. useTemplates for pod and volume templates")
def test_002():
    create_and_check("configs/test-002-tpl.yaml", 
                     {"pod_count": 1,
                      "apply_templates": {"configs/tpl-clickhouse-stable.yaml", "configs/tpl-log-volume.yaml"},
                      "pod_image": clickhouse_stable,
                      "pod_volumes": {"/var/log/clickhouse-server"}})

@TestScenario
@Name("test_003. useTemplates for pod and distribution templates")
def test_003():
    create_and_check("configs/test-003-tpl.yaml", 
                     {"pod_count": 1,
                      "apply_templates": {"configs/tpl-clickhouse-stable.yaml", "configs/tpl-one-per-host.yaml"},
                      "pod_image": clickhouse_stable,
                      "pod_podAntiAffinity": 1})

@TestScenario
@Name("test_004. Compatibility test if old syntax with volumeClaimTemplate is still supported")
def test_004():
    create_and_check("configs/test-004-tpl.yaml", 
                     {"pod_count": 1,
                      "pod_volumes": {"/var/lib/clickhouse"}})

@TestScenario
@Name("test_005. Test manifest created by ACM")
def test_005():
    create_and_check("configs/test-005-acm.yaml", 
                     {"pod_count": 1,
                      "pod_image": "yandex/clickhouse-server:19.11.8.46",
                      "pod_volumes": {"/var/lib/clickhouse"}})

@TestScenario
@Name("test_006. Test clickhouse version upgrade from one version to another using podTemplate change")
def test_006():
    create_and_check("configs/test-006-ch-upgrade-1.yaml", 
                     {"pod_count": 2,
                      "pod_image": "yandex/clickhouse-server:19.11.8.46",
                      "do_not_delete": 1})
    with Then("Use different podTemplate and confirm that pod image is updated"):  
        create_and_check("configs/test-006-ch-upgrade-2.yaml", 
                         {"pod_count": 2,
                          "pod_image": "yandex/clickhouse-server:latest",
                          "do_not_delete": 1})
        with Then("Change image in podTemplate itself and confirm that pod image is updated"):
            create_and_check("configs/test-006-ch-upgrade-3.yaml", 
                             {"pod_count": 2,
                              "pod_image": "yandex/clickhouse-server:19.11.8.46"})

@TestScenario
@Name("test_007. Test template with custom clickhouse ports")
def test_007():
    create_and_check("configs/test-007-custom-ports.yaml", 
                     {"pod_count": 1,
                      "apply_templates": {"configs/tpl-custom-ports.yaml"},
                      "pod_image": "yandex/clickhouse-server:19.11.8.46",
                      "pod_ports": [8124,9001,9010]})

@TestScenario
@Name("test_009. Test operator upgrade from 0.6.0 to later version")
def test_009():
    version_from="0.6.0"
    version_to="dev"
    with Given(f"clickhouse-operator {version_from}"):
        set_operator_version(version_from)
        config=get_full_path("configs/test-009-long-name.yaml")
        chi_full_name=get_chi_name(config)
        chi_cut_name=chi_full_name[0:15]

        kube_apply(config)
        kube_wait_objects(chi_cut_name, [1,1,2])
        kube_wait_chi_status(chi_full_name, "Completed")
        
        assert kube_get_count("statefulset", label = "-l clickhouse.altinity.com/app=chop")==1, error()
        
        with Then(f"upgrade operator to {version_to}"):
            set_operator_version(version_to)
            with And("Wait 20 seconds"):
                time.sleep(20)
                with Then("No new statefulsets should be created"):
                    assert kube_get_count("statefulset", label = "-l clickhouse.altinity.com/app=chop")==1, error()

        
        
def set_operator_version(version):
    kubectl(f"set image deployment.v1.apps/clickhouse-operator clickhouse-operator=altinity/clickhouse-operator:{version}", ns = "kube-system")
    kubectl("rollout status deployment.v1.apps/clickhouse-operator", ns = "kube-system")
    # assert kube_get_count("pod", ns = "kube-system", label = f"-l app=clickhouse-operator,version={version}")>0, error()

def check_zookeeper():
    with Given("Install Zookeeper if missing"):
        if kube_get_count("service", name = "zookeepers") == 0:
            config=get_full_path("../deploy/zookeeper/quick-start-volume-emptyDir/zookeeper-1-node.yaml")
            kube_apply(config)
            kube_wait_object("pod", "zookeeper-0")
            kube_wait_pod_status("zookeeper-0", "Running")

@TestScenario
@Name("test_010. Test zookeeper initialization")
def test_010():
    check_zookeeper()

    create_and_check("configs/test-010-zkroot.yaml", 
                     {"apply_templates": {"configs/tpl-clickhouse-stable.yaml"},
                      "pod_count": 1,
                      "do_not_delete": 1})
    with And("ClickHouse should complain regarding zookeeper path"):
        out = clickhouse_query_with_error("test-010-zkroot", "select * from system.zookeeper where path = '/'")
        assert "You should create root node /clickhouse/test-010-zkroot before start" in out, error()
    
    create_and_check("configs/test-010-zkroot.yaml",{})

@TestScenario
@Name("test_011. Test user security and network isolation")    
def test_011():
    
    with Given("test-011-secured-cluster.yaml and test-011-insecured-cluster.yaml"):
        create_and_check("configs/test-011-secured-cluster.yaml", 
                         {"pod_count": 2,
                          "apply_templates": {"configs/tpl-log-volume.yaml"},
                          "do_not_delete": 1})

        create_and_check("configs/test-011-insecured-cluster.yaml", 
                        {"pod_count": 1,
                         "do_not_delete": 1})

        with Then("Connection to localhost should succeed with default user"):
            out = clickhouse_query_with_error("test-011-secured-cluster", "select 'OK'")
            assert out == 'OK'

        with And("Connection from secured to secured host should succeed"):
            out = clickhouse_query_with_error("test-011-secured-cluster", "select 'OK'", 
                                              host = "chi-test-011-secured-cluster-default-1-0")
            assert out == 'OK'

        with And("Connection from insecured to secured host should fail for default"):
            out = clickhouse_query_with_error("test-011-insecured-cluster","select 'OK'", 
                                              host = "chi-test-011-secured-cluster-default-1-0")
            assert out != 'OK'

        with And("Connection from insecured to secured host should fail for user with no password"):
            out = clickhouse_query_with_error("test-011-insecured-cluster","select 'OK'", 
                                              host = "chi-test-011-secured-cluster-default-1-0", user = "user1")
            assert "Password required" in out
    
        with And("Connection from insecured to secured host should work for user with password"):
            out = clickhouse_query_with_error("test-011-insecured-cluster","select 'OK'", 
                                              host = "chi-test-011-secured-cluster-default-1-0", user = "user1", pwd = "topsecret")
            assert out == 'OK'

        with And("Password should be encrypted"):
            chi = kube_get("chi", "test-011-secured-cluster")
            assert "user1/password" not in chi["spec"]["configuration"]["users"]
            assert "user1/password_sha256_hex" in chi["spec"]["configuration"]["users"]

        with And("User with no password should get default automatically"):
            out = clickhouse_query_with_error("test-011-secured-cluster", "select 'OK'", user = "user2", pwd = "default")
            assert out == 'OK'

        with And("User with both plain and sha256 password should get the latter one"):
            out = clickhouse_query_with_error("test-011-secured-cluster", "select 'OK'", user = "user3", pwd = "clickhouse_operator_password")
            assert out == 'OK'
        
        with And("Password should be encrypted"):
            chi = kube_get("chi", "test-011-secured-cluster")
            assert "user3/password" not in chi["spec"]["configuration"]["users"]
            assert "user3/password_sha256_hex" in chi["spec"]["configuration"]["users"]

        create_and_check("configs/test-011-secured-cluster.yaml", {})
        create_and_check("configs/test-011-insecured-cluster.yaml", {})
    
    with Given("test-011-secured-default.yaml"):
        create_and_check("configs/test-011-secured-default.yaml", 
                         {"pod_count": 1,
                          "do_not_delete": 1})

        with Then("Default user password should be '_removed_'"):
            chi = kube_get("chi", "test-011-secured-default")
            assert "default/password" in chi["spec"]["configuration"]["users"]
            assert chi["spec"]["configuration"]["users"]["default/password"] == "_removed_"
    
        with And("Connection to localhost should succeed with default user"):
            out = clickhouse_query_with_error("test-011-secured-default", "select 'OK'", pwd = "clickhouse_operator_password")
            assert out == 'OK'
    
        with When("Trigger installation update"):
            create_and_check("configs/test-011-secured-default-2.yaml", {"do_not_delete": 1})
            with Then("Default user password should be '_removed_'"):
                chi = kube_get("chi", "test-011-secured-default")
                assert "default/password" in chi["spec"]["configuration"]["users"]
                assert chi["spec"]["configuration"]["users"]["default/password"] == "_removed_"
    
        create_and_check("configs/test-011-secured-default.yaml", {})


@TestScenario
@Name("test_012. Test service templates")
def test_012():
    create_and_check("configs/test-012-service-template.yaml", 
                     {"object_counts": [2,2,4],
                      "service": ["service-test-012","ClusterIP"],
                      "do_not_delete": 1})
    with Then("There should be a service for shard 0"):
        kube_check_service("service-test-012-0-0","ClusterIP")
    with And("There should be a service for shard 1"):
        kube_check_service("service-test-012-1-0","ClusterIP")
    with And("There should be a service for default cluster"):
        kube_check_service("service-default","ClusterIP")

    create_and_check("configs/test-012-service-template.yaml", {})

@TestScenario
@Name("test_013. Test adding shards and creating local and distributed tables automatically")
def test_013():
    create_and_check("configs/test-013-add-shards-1.yaml",
                     {"apply_templates": {"configs/tpl-clickhouse-stable.yaml"}, 
                      "object_counts": [1,1,2], "do_not_delete": 1})
    
    with Then("Create local and distributed table"):
        clickhouse_query("test-013-add-shards", 
                         "CREATE TABLE test_local Engine = Log as select * from system.one")
        clickhouse_query("test-013-add-shards", 
                         "CREATE TABLE test_distr as test_local Engine = Distributed('default', default, test_local)")

    with Then("Add one more shard"):
        create_and_check("configs/test-013-add-shards-2.yaml", {"object_counts": [2,2,3], "do_not_delete": 1})
    with And("Table should be created on a second shard"):
        out = clickhouse_query("test-013-add-shards", "select count() from default.test_distr",
                               host = "chi-test-013-add-shards-default-1-0")
        assert out == "1"
    
    with Then("Remove shard"):
        create_and_check("configs/test-013-add-shards-1.yaml", {"object_counts": [1,1,2]})

@TestScenario
@Name("test_014. Test that replication works")
def test_014():
    check_zookeeper()
 
    create_table = """
    create table t (a Int8) 
    Engine = ReplicatedMergeTree('/clickhouse/{installation}/{cluster}/tables/{shard}/{database}/{table}', '{replica}')
    partition by tuple() order by a""".replace('\r', '').replace('\n', '')

    create_and_check("configs/test-014-replication.yaml", 
                    {"apply_templates": {"configs/tpl-clickhouse-stable.yaml"}, 
                     "pod_count": 2,
                     "do_not_delete": 1})

    clickhouse_query("test-014-replication", create_table, host = "chi-test-014-replication-default-0-0")
    clickhouse_query("test-014-replication", "insert into t values(1)", host = "chi-test-014-replication-default-0-0")
    clickhouse_query("test-014-replication", create_table, host = "chi-test-014-replication-default-0-1")
    out = clickhouse_query("test-014-replication", "select a from t", host = "chi-test-014-replication-default-0-1")
    assert out == "1"

    with When("Add one more replica"):
        create_and_check("configs/test-014-replication-2.yaml", 
                         {"pod_count": 3,
                          "do_not_delete": 1})
        # that also works:
        # kubectl patch chi test-014-replication -n test --type=json -p '[{"op":"add", "path": "/spec/configuration/clusters/0/layout/shards/0/replicasCount", "value": 3}]'
        with Then("Replicated table should be automatically created"):
            out = clickhouse_query("test-014-replication", "select a from t", host = "chi-test-014-replication-default-0-2")
            assert out == "1"

    create_and_check("configs/test-014-replication.yaml", {})

@TestScenario
@Name("test_015. Test circular replication with hostNetwork")
def test_015():
    create_and_check("configs/test-015-host-network.yaml", 
                     {"pod_count": 2,
                      "do_not_delete": 1})
    
    with Then("Query from one server to another one should work"):
        clickhouse_query("test-015-host-network", host = "chi-test-015-host-network-default-0-0", port = "10000", 
                            query = "select * from remote('chi-test-015-host-network-default-0-1', system.one)")
    
    with Then("Distributed query should work"):
        out = clickhouse_query("test-015-host-network", host = "chi-test-015-host-network-default-0-0", port = "10000", 
                               query = "select count() from cluster('all-sharded', system.one) settings receive_timeout=10")
        assert out == "2"
    
    create_and_check("configs/test-015-host-network.yaml", {})


kubectl.namespace="test"
version="0.9.0"
clickhouse_stable="yandex/clickhouse-server:19.16.10.44"

if main():
    with Module("main"):
        with Given("clickhouse-operator is installed"):
            # assert kube_get_count("pod", ns = "kube-system", label = "-l app=clickhouse-operator")>0, error()
            with And(f"Set operator version {version}"):
                set_operator_version(version)
            with And(f"Clean namespace {kubectl.namespace}"): 
                kube_deletens(kubectl.namespace)
                with And(f"Create namespace {kubectl.namespace}"):
                    kube_createns(kubectl.namespace)
    
    #    with Module("examples", flags=TE):
    #        examples=[test_examples01_1, test_examples01_2, test_examples02_1, test_examples02_2]
    #        for t in examples:
    #            run(test=t, flags=TE)
        
        with Module("regression", flags=TE):
            tests = [test_001, 
                     test_002, 
                     test_003,
                     test_004, 
                     test_005, 
                     test_006, 
                     test_007,
                     # test_009,  
                     test_010,
                     test_011,
                     test_012,
                     test_013,
                     test_014,
                     test_015]
        
            all_tests = tests
            # all_tests = [test_012]
        
            for t in all_tests:
                run(test=t, flags=TE)

