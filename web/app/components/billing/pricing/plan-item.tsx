'use client'
import type { FC } from 'react'
import React from 'react'
import { useTranslation } from 'react-i18next'
import cn from 'classnames'
import { Plan } from '../type'
import Toast from '../../base/toast'
import { PlanRange } from './select-plan-range'
import { ALL_PLANS, NUM_INFINITE } from '@/app/components/billing/config'
import { useAppContext } from '@/context/app-context'

type Props = {
  currentPlan: Plan
  plan: Plan
  planRange: PlanRange
  link: string
}

const KeyValue = ({ label, value }: { label: string; value: string | number | JSX.Element }) => {
  return (
    <div className='mt-3.5 leading-[125%] text-[13px] font-medium'>
      <div className='text-gray-500'>{label}</div>
      <div className='mt-0.5 text-gray-900'>{value}</div>
    </div>
  )
}

const priceClassName = 'leading-[32px] text-[28px] font-bold text-gray-900'
const style = {
  [Plan.sandbox]: {
    bg: 'bg-[#F2F4F7]',
    title: 'text-gray-900',
    hoverAndActive: '',
  },
  [Plan.professional]: {
    bg: 'bg-[#E0F2FE]',
    title: 'text-[#026AA2]',
    hoverAndActive: 'hover:shadow-lg hover:!text-white hover:!bg-[#0086C9] hover:!border-[#026AA2] active:!text-white active:!bg-[#026AA2] active:!border-[#026AA2]',
  },
  [Plan.team]: {
    bg: 'bg-[#E0EAFF]',
    title: 'text-[#3538CD]',
    hoverAndActive: 'hover:shadow-lg hover:!text-white hover:!bg-[#444CE7] hover:!border-[#3538CD] active:!text-white active:!bg-[#3538CD] active:!border-[#3538CD]',
  },
  [Plan.enterprise]: {
    bg: 'bg-[#FFEED3]',
    title: 'text-[#DC6803]',
    hoverAndActive: 'hover:shadow-lg hover:!text-white hover:!bg-[#F79009] hover:!border-[#DC6803] active:!text-white active:!bg-[#DC6803] active:!border-[#DC6803]',
  },
}
const PlanItem: FC<Props> = ({
  plan,
  currentPlan,
  planRange,
  link,
}) => {
  const { t } = useTranslation()
  const i18nPrefix = `billing.plans.${plan}`
  const isFreePlan = plan === Plan.sandbox
  const isEnterprisePlan = plan === Plan.enterprise
  const isMostPopularPlan = plan === Plan.professional
  const planInfo = ALL_PLANS[plan]
  const isYear = planRange === PlanRange.yearly
  const isCurrent = plan === currentPlan
  const isPlanDisabled = planInfo.level <= ALL_PLANS[currentPlan].level
  const { isCurrentWorkspaceManager } = useAppContext()

  const btnText = (() => {
    if (isCurrent)
      return t('billing.plansCommon.currentPlan')

    return ({
      [Plan.sandbox]: t('billing.plansCommon.startForFree'),
      [Plan.professional]: <>{t('billing.plansCommon.getStartedWith')}<span className='capitalize'>&nbsp;{plan}</span></>,
      [Plan.team]: <>{t('billing.plansCommon.getStartedWith')}<span className='capitalize'>&nbsp;{plan}</span></>,
      [Plan.enterprise]: t('billing.plansCommon.talkToSales'),
    })[plan]
  })()
  const comingSoon = (
    <div className='leading-[12px] text-[9px] font-semibold text-[#3538CD] uppercase'>{t('billing.plansCommon.comingSoon')}</div>
  )
  const supportContent = (() => {
    switch (plan) {
      case Plan.sandbox:
        return t('billing.plansCommon.supportItems.communityForums')
      case Plan.professional:
        return t('billing.plansCommon.supportItems.emailSupport')
      case Plan.team:
        return (
          <div>
            <div>{t('billing.plansCommon.supportItems.priorityEmail')}</div>
            <div className='mt-3.5 flex items-center space-x-1'>
              <div>+ {t('billing.plansCommon.supportItems.logoChange')}</div>
              <div>{comingSoon}</div>
            </div>
            <div className='mt-3.5 flex items-center space-x-1'>
              <div>+ {t('billing.plansCommon.supportItems.personalizedSupport')}</div>
              <div>{comingSoon}</div>
            </div>
          </div>
        )
      case Plan.enterprise:
        return (
          <div>
            <div>{t('billing.plansCommon.supportItems.personalizedSupport')}</div>
            <div className='mt-3.5 flex items-center space-x-1'>
              <div>+ {t('billing.plansCommon.supportItems.dedicatedAPISupport')}</div>
            </div>
            <div className='mt-3.5 flex items-center space-x-1'>
              <div>+ {t('billing.plansCommon.supportItems.customIntegration')}</div>
            </div>
          </div>
        )
      default:
        return ''
    }
  })()
  return (
    <div className={cn(isMostPopularPlan ? 'bg-[#0086C9] p-0.5' : 'pt-7', 'flex flex-col min-w-[290px] w-[290px] h-[712px] rounded-xl')}>
      {isMostPopularPlan && (
        <div className='flex items-center h-7 justify-center leading-[12px] text-xs font-medium text-[#F5F8FF]'>{t('billing.plansCommon.mostPopular')}</div>
      )}
      <div className={cn(style[plan].bg, 'grow px-6 pt-6 rounded-[10px]')}>
        <div className={cn(style[plan].title, 'mb-1 leading-[125%] text-lg font-semibold')}>{t(`${i18nPrefix}.name`)}</div>
        <div className={cn(isFreePlan ? 'text-[#FB6514]' : 'text-gray-500', 'mb-4 h-8 leading-[125%] text-[13px] font-normal')}>{t(`${i18nPrefix}.description`)}</div>

        {/* Price */}
        {isFreePlan && (
          <div className={priceClassName}>{t('billing.plansCommon.free')}</div>
        )}
        {isEnterprisePlan && (
          <div className={priceClassName}>{t('billing.plansCommon.contactSales')}</div>
        )}
        {!isFreePlan && !isEnterprisePlan && (
          <div className='flex items-end h-9'>
            <div className={priceClassName}>${isYear ? planInfo.price * 10 : planInfo.price}</div>
            <div className='ml-1'>
              {isYear && <div className='leading-[18px] text-xs font-medium text-[#F26725]'>{t('billing.plansCommon.save')}${planInfo.price * 2}</div>}
              <div className='leading-[18px] text-[15px] font-normal text-gray-500'>/{t(`billing.plansCommon.${!isYear ? 'month' : 'year'}`)}</div>
            </div>
          </div>
        )}

        <div
          className={cn(isMostPopularPlan && !isCurrent && '!bg-[#444CE7] !text-white !border !border-[#3538CD] shadow-sm', isPlanDisabled ? 'opacity-30' : `${style[plan].hoverAndActive} cursor-pointer`, 'mt-4 flex h-11 items-center justify-center border-[2px] border-gray-900 rounded-3xl text-sm font-semibold text-gray-900')}
          onClick={() => {
            if (isPlanDisabled)
              return
            // Only workspace manager can buy plan
            if (!isCurrentWorkspaceManager) {
              Toast.notify({
                type: 'error',
                message: t('billing.buyPermissionDeniedTip'),
                className: 'z-[1001]',
              })
              return
            }
            window.open(link, '_self')
          }}
        >
          {btnText}
        </div>

        <div className='my-4 h-[1px] bg-black/5'></div>

        <div className='leading-[125%] text-[13px] font-normal text-gray-900'>
          {t(`${i18nPrefix}.includesTitle`)}
        </div>
        <KeyValue
          label={t('billing.plansCommon.modelProviders')}
          value={planInfo.modelProviders}
        />
        <KeyValue
          label={t('billing.plansCommon.teamMembers')}
          value={planInfo.teamMembers === NUM_INFINITE ? t('billing.plansCommon.unlimited') as string : planInfo.teamMembers}
        />
        <KeyValue
          label={t('billing.plansCommon.buildApps')}
          value={planInfo.buildApps === NUM_INFINITE ? t('billing.plansCommon.unlimited') as string : planInfo.buildApps}
        />
        <KeyValue
          label={t('billing.plansCommon.vectorSpace')}
          value={planInfo.vectorSpace === NUM_INFINITE ? t('billing.plansCommon.unlimited') as string : (planInfo.vectorSpace >= 1000 ? `${planInfo.vectorSpace / 1000}G` : `${planInfo.vectorSpace}MB`)}
        />
        <KeyValue
          label={t('billing.plansCommon.documentProcessingPriority')}
          value={t(`billing.plansCommon.priority.${planInfo.documentProcessingPriority}`) as string}
        />
        <KeyValue
          label={t('billing.plansCommon.logsHistory')}
          value={planInfo.logHistory === NUM_INFINITE ? t('billing.plansCommon.unlimited') as string : `${planInfo.logHistory} ${t('billing.plansCommon.days')}`}
        />
        <KeyValue
          label={t('billing.plansCommon.support')}
          value={supportContent}
        />
      </div>
    </div>
  )
}
export default React.memo(PlanItem)