"""
Architecture diagrams for LTT infrastructure.
Run: python3 docs/architecture/diagrams/generate.py
Output: docs/architecture/diagrams/*.png
"""

import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECS, ECR
from diagrams.aws.database import RDS, ElastiCache
from diagrams.aws.network import ALB, VPC
from diagrams.aws.security import SecretsManager
from diagrams.aws.management import Cloudwatch
from diagrams.aws.storage import S3
from diagrams.aws.devtools import Codebuild
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.network import Nginx
from diagrams.onprem.client import Users

GRAPH_ATTR = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "0.5",
    "splines": "ortho",
    "nodesep": "0.6",
    "ranksep": "0.8",
}

# ─────────────────────────────────────────────
# Diagram 1: Overall traffic flow
# ─────────────────────────────────────────────
with Diagram(
    "LTT — Traffic Flow",
    filename="traffic-flow",
    outformat="png",
    graph_attr={**GRAPH_ATTR, "rankdir": "LR"},
    show=False,
):
    learner = Users("Learner\n(browser)")
    lms = Users("Open edX\n(imbizo.alx-ai-tools.com)")

    with Cluster("AWS eu-west-1"):
        with Cluster("Bastion (52.30.100.225)"):
            nginx = Nginx("nginx\nSSL termination\nhost-header routing")

        with Cluster("VPC 10.0.0.0/16"):
            with Cluster("ltt-nonprod ALB (internal)"):
                alb_nonprod = ALB("ltt-nonprod ALB")

            with Cluster("ltt-prod ALB (internal)"):
                alb_prod = ALB("ltt-prod ALB")

            with Cluster("ltt-dev ECS cluster"):
                ecs_dev_be = ECS("backend :8000")
                ecs_dev_fe = ECS("frontend :3000")

            with Cluster("ltt-staging ECS cluster"):
                ecs_stg_be = ECS("backend :8000")
                ecs_stg_fe = ECS("frontend :3000")

            with Cluster("ltt-prod ECS cluster"):
                ecs_prod_be = ECS("backend :8000")
                ecs_prod_fe = ECS("frontend :3000")

    learner >> nginx
    lms >> nginx
    nginx >> alb_nonprod
    nginx >> alb_prod
    alb_nonprod >> Edge(label="dev-mwongozo.*") >> ecs_dev_be
    alb_nonprod >> Edge(label="dev-mwongozo.*") >> ecs_dev_fe
    alb_nonprod >> Edge(label="staging-mwongozo.*") >> ecs_stg_be
    alb_nonprod >> Edge(label="staging-mwongozo.*") >> ecs_stg_fe
    alb_prod >> Edge(label="mwongozo.*") >> ecs_prod_be
    alb_prod >> Edge(label="mwongozo.*") >> ecs_prod_fe


# ─────────────────────────────────────────────
# Diagram 2: Dev/Staging shared infrastructure
# ─────────────────────────────────────────────
with Diagram(
    "LTT — Dev/Staging Infrastructure",
    filename="dev-staging-infra",
    outformat="png",
    graph_attr={**GRAPH_ATTR, "rankdir": "TB"},
    show=False,
):
    with Cluster("AWS eu-west-1 — dev-staging environment"):

        with Cluster("ECR"):
            ecr_be = ECR("ltt-backend")
            ecr_fe = ECR("ltt-frontend")

        with Cluster("ltt-nonprod ALB\nhost-header routing"):
            alb = ALB("ltt-nonprod ALB")

        with Cluster("ltt-dev ECS cluster"):
            dev_fe = ECS("frontend :3000\nNext.js")
            dev_be = ECS("backend :8000\nFastAPI")
            dev_migrate = ECS("migrate\n(one-off)")

        with Cluster("ltt-staging ECS cluster"):
            stg_fe = ECS("frontend :3000\nNext.js")
            stg_be = ECS("backend :8000\nFastAPI")
            stg_migrate = ECS("migrate\n(one-off)")

        with Cluster("Shared Data (dev-staging)"):
            rds = RDS("ltt-nonprod RDS\nPostgreSQL 17\ndb.t4g.micro\n─────────────\nltt_dev\nltt_dev_checkpoints\nltt_staging\nltt_staging_checkpoints")
            redis = ElastiCache("ltt-nonprod Redis 7\ncache.t4g.micro\n─────────────\ndb0 = dev\ndb1 = staging")

        with Cluster("Secrets Manager"):
            secrets_dev = SecretsManager("ltt/dev/*\n7 secrets")
            secrets_stg = SecretsManager("ltt/staging/*\n7 secrets")

        with Cluster("CloudWatch"):
            logs_dev = Cloudwatch("/ecs/ltt-dev-*")
            logs_stg = Cloudwatch("/ecs/ltt-staging-*")

    alb >> Edge(label="dev-mwongozo\n/api/* → :8000\n/* → :3000") >> dev_be
    alb >> dev_fe
    alb >> Edge(label="staging-mwongozo\n/api/* → :8000\n/* → :3000") >> stg_be
    alb >> stg_fe

    dev_be >> rds
    dev_be >> redis
    stg_be >> rds
    stg_be >> redis

    dev_migrate >> rds
    stg_migrate >> rds

    ecr_be >> dev_be
    ecr_be >> stg_be
    ecr_be >> dev_migrate
    ecr_be >> stg_migrate
    ecr_fe >> dev_fe
    ecr_fe >> stg_fe

    secrets_dev >> dev_be
    secrets_stg >> stg_be

    dev_be >> logs_dev
    dev_fe >> logs_dev
    stg_be >> logs_stg
    stg_fe >> logs_stg


# ─────────────────────────────────────────────
# Diagram 3: Production infrastructure
# ─────────────────────────────────────────────
with Diagram(
    "LTT — Production Infrastructure",
    filename="prod-infra",
    outformat="png",
    graph_attr={**GRAPH_ATTR, "rankdir": "TB"},
    show=False,
):
    with Cluster("AWS eu-west-1 — prod environment"):

        with Cluster("ECR"):
            ecr_be = ECR("ltt-backend")
            ecr_fe = ECR("ltt-frontend")

        with Cluster("ltt-prod ALB"):
            alb = ALB("ltt-prod ALB")

        with Cluster("ltt-prod ECS cluster\n(desired=2, autoscale to 4)"):
            prod_fe = ECS("frontend :3000\nNext.js")
            prod_be = ECS("backend :8000\nFastAPI × 2")
            prod_migrate = ECS("migrate\n(one-off)")

        with Cluster("Dedicated Data"):
            rds = RDS("ltt-prod RDS\nPostgreSQL 17\nMulti-AZ\ndb.t4g.small\n─────────────\nltt_prod\nltt_prod_checkpoints")
            redis = ElastiCache("ltt-prod Redis 7\ncache.t4g.micro")

        with Cluster("Secrets Manager"):
            secrets = SecretsManager("ltt/prod/*\n7 secrets")

        with Cluster("CloudWatch"):
            logs = Cloudwatch("/ecs/ltt-prod-*\nalarms: CPU > 70%\nMemory > 80%")

    alb >> Edge(label="mwongozo.alx-ai-tools.com\n/api/* /lti/* → :8000\n/* → :3000") >> prod_be
    alb >> prod_fe

    prod_be >> rds
    prod_be >> redis
    prod_migrate >> rds

    ecr_be >> prod_be
    ecr_be >> prod_migrate
    ecr_fe >> prod_fe

    secrets >> prod_be

    prod_be >> logs
    prod_fe >> logs


# ─────────────────────────────────────────────
# Diagram 4: CI/CD deploy pipeline
# ─────────────────────────────────────────────
with Diagram(
    "LTT — CI/CD Pipeline",
    filename="cicd-pipeline",
    outformat="png",
    graph_attr={**GRAPH_ATTR, "rankdir": "LR"},
    show=False,
):
    dev = Users("Developer")

    with Cluster("GitHub"):
        gh = GithubActions("GitHub Actions\ndeploy.yml")
        repo = Codebuild("git push\nenv-dev / env-staging\nenv-prod")

    with Cluster("AWS eu-west-1"):
        ecr = ECR("ECR\nltt-backend\nltt-frontend")

        with Cluster("ECS (target env)"):
            migrate = ECS("migrate task\ndb ensure-databases\nalembic upgrade head")
            service = ECS("backend + frontend\nrolling deploy")

        secrets = SecretsManager("Secrets Manager\nltt/{env}/*")
        logs = Cloudwatch("CloudWatch\n/ecs/ltt-{env}-*")
        s3 = S3("S3\nTerraform state")

    dev >> repo >> gh
    gh >> Edge(label="1. build & push\nDocker images") >> ecr
    gh >> Edge(label="2. run migrations") >> migrate
    migrate >> secrets
    gh >> Edge(label="3. register new\ntask definition\n(image + env vars)") >> service
    service >> secrets
    service >> logs
    gh >> s3

print("Diagrams generated:")
import glob
for f in sorted(glob.glob("*.png")):
    size = os.path.getsize(f)
    print(f"  {f}  ({size // 1024} KB)")
